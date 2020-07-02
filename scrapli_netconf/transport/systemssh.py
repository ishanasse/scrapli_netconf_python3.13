"""scrapli_netconf.transport.systemssh"""
from typing import Any

from scrapli.decorators import operation_timeout
from scrapli.exceptions import ScrapliAuthenticationFailed
from scrapli.transport import SystemSSHTransport
from scrapli.transport.ptyprocess import PtyProcess


class NetconfSystemSSHTransport(SystemSSHTransport):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def _build_open_cmd(self) -> None:
        super()._build_open_cmd()
        self.open_cmd.extend(["-s", "netconf"])

    def open_netconf(self) -> bytes:
        """
        Netconf open method

        Several of the base SystemSSHTransport methods must be overridden in order to capture output
        of server capabilities that must be parsed.

        Args:
            N/A

        Returns:
            bytes: bytes output from server captured while opening the connection

        Raises:
            N/A

        """
        login_bytes = self._open_netconf_pty()

        if self.keepalive:
            self._session_keepalive()

        return login_bytes

    def _open_netconf_pty(self) -> bytes:
        """
        Private method to open session with PtyProcess

        Args:
            N/A

        Returns:
            bytes: any output captured during login/authentication; needed to build server
                capabilities

        Raises:
            N/A

        """
        self.session = PtyProcess.spawn(self.open_cmd)
        self.logger.debug(f"Session to host {self.host} spawned")
        login_bytes: bytes = self._authenticate()
        self.logger.debug(f"Authenticated to host {self.host} successfully")
        return login_bytes

    @operation_timeout("_timeout_ops", "Timed out looking for SSH login password prompt")
    def _authenticate(self) -> bytes:
        """
        Private method to check initial authentication when using pty_session

        Args:
            N/A

        Returns:
            N/A  # noqa: DAR202

        Raises:
            ScrapliAuthenticationFailed: if we see a password prompt more than once, or we got an
                unhandled EOF message

        """
        self.session_lock.acquire()
        output = b""
        password_count = 0
        while True:
            try:
                new_output = self.session.read()
                output += new_output
                self.logger.debug(f"Attempting to authenticate. Read: {repr(new_output)}")
            except EOFError:
                self._ssh_message_handler(output=output)
                # if _ssh_message_handler didn't raise any exception, we can raise the standard --
                # did you disable strict key message/exception
                msg = (
                    f"Failed to open connection to host {self.host}. Do you need to disable "
                    "`auth_strict_key`?"
                )
                self.logger.critical(msg)
                self.session_lock.release()
                raise ScrapliAuthenticationFailed(msg)
            if b"password:" in output.lower():
                # if password is seen in the output, reset output and enter the password
                # count the times password occurs to have a decent idea if auth failed
                password_count += 1
                output = b""
                self.logger.info("Found password prompt, sending password")
                self.session.write(self.auth_password.encode())
                self.session.write(self._comms_return_char.encode())
            if password_count > 1:
                msg = (
                    "`password` seen multiple times during session establishment, "
                    "likely failed authentication"
                )
                self.session_lock.release()
                raise ScrapliAuthenticationFailed(msg)
            if b"<hello" in output.lower():
                self.logger.info("Found start of server capabilities, authentication successful")
                self._isauthenticated = True
                self.session_lock.release()
                return output

    def _keepalive_network(self) -> None:
        """
        Override _keepalive_network from scrapli; not supported with netconf

        Args:
            N/A

        Returns:
            N/A  # noqa: DAR202

        Raises:
            NotImplementedError: always for now...

        """
        raise NotImplementedError("`network` style keepalives not supported with netconf")

    def _keepalive_standard(self) -> None:
        """
        Send "out of band" (protocol level) keepalives to devices.

        Args:
            N/A

        Returns:
            N/A  # noqa: DAR202

        Raises:
            NotImplementedError: always for now...

        """
        raise NotImplementedError("keepalives not yet implemented")
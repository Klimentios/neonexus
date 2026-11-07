"""A room restart must not cut the agents off: the MCP HTTP server keeps no sessions."""
import unittest

import mcp_bridge


class McpRestartTests(unittest.TestCase):
    def test_http_server_is_stateless(self):
        self.assertTrue(mcp_bridge.mcp_http.settings.stateless_http)


if __name__ == "__main__":
    unittest.main()

"""The DIY endpoint uses success code 200 while existing APIs use zero."""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("diy_test_lib")
package.__path__ = [str(ROOT / "custom_components/midea_smart_home/midea_lib")]
sys.modules[package.__name__] = package
CLOUD = importlib.import_module("diy_test_lib.cloud")


class DiyCloudTests(unittest.IsolatedAsyncioTestCase):
    def client(self, code=200, data=None):
        response = Mock()
        response.read = AsyncMock(return_value=json.dumps({"code": code, "data": data or {"hisRes": []}}).encode())
        session = Mock()
        session.request = AsyncMock(return_value=response)
        cloud = CLOUD.get_midea_cloud("Meiju Cloud", session, "fixture-account", "fixture-password")
        cloud._uid = "fixture-user"
        return cloud, session

    async def test_diy_success_code_and_exact_request(self):
        cloud, session = self.client()
        self.assertEqual(await cloud.list_diy_programs(123, "700XG241", "V0.0.0"), {"hisRes": []})
        args, kwargs = session.request.call_args
        self.assertTrue(args[1].endswith("/cloud-menu/midea/menu/dev/diymode/get/new"))
        body = json.loads(kwargs["data"])
        self.assertEqual(body["deviceId"], "123")
        self.assertEqual(body["sn8"], "700XG241")
        self.assertEqual(body["userId"], "fixture-user")

    async def test_existing_apis_still_reject_code_200(self):
        cloud, _ = self.client()
        self.assertIsNone(await cloud._api_request("/fixture", {}))

    async def test_failed_diy_query_is_not_an_empty_program_list(self):
        cloud, _ = self.client(code=401)
        self.assertIsNone(await cloud.list_diy_programs(123, "700XG241"))

    async def test_zero_code_is_also_supported(self):
        cloud, _ = self.client(code=0)
        self.assertEqual(await cloud.list_diy_programs(123, "700XG241"), {"hisRes": []})


if __name__ == "__main__":
    unittest.main()

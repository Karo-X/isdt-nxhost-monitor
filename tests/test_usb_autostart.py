from pathlib import Path
import unittest

from usb_autostart import (
    LABEL,
    USB_NAME,
    USB_PRODUCT_ID,
    USB_VENDOR_ID,
    launch_agent_payload,
    usb_signature_matches,
)


class USBAutostartTests(unittest.TestCase):
    def test_matches_observed_isdtnx_signature(self):
        output = f'''\n+-o ISDTNX <class IOUSBHostDevice>\n    {{\n      "idProduct" = {USB_PRODUCT_ID}\n      "USB Product Name" = "{USB_NAME}"\n      "idVendor" = {USB_VENDOR_ID}\n    }}\n'''
        self.assertTrue(usb_signature_matches(output))
        self.assertFalse(usb_signature_matches(output.replace('"idProduct" = 650', '"idProduct" = 651')))

    def test_launch_agent_stays_local_and_uses_project_python(self):
        project = Path("/tmp/isdt-nxhost-monitor")
        python = Path("/Users/example/isdt-env/bin/python")
        payload = launch_agent_payload(project, python)
        self.assertEqual(payload["Label"], LABEL)
        self.assertEqual(payload["ProgramArguments"][0], str(python))
        self.assertEqual(payload["ProgramArguments"][1], str(project / "usb_autostart.py"))
        self.assertEqual(payload["ProgramArguments"][2], "--watch")
        self.assertTrue(payload["RunAtLoad"])
        self.assertTrue(payload["KeepAlive"])


if __name__ == "__main__":
    unittest.main()

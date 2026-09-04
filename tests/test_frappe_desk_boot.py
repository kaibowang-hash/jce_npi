from __future__ import annotations

import sys
import unittest


sys.path.insert(0, "apps/npi_core")

from npi_core.hooks import strip_desk_boot_jinja_messages


class FrappeDeskBootTests(unittest.TestCase):
    def test_spa_placeholders_are_excluded_from_desk_boot(self) -> None:
        bootinfo = {
            "assets_json": {},
            "__messages": {
                "Save": "保存",
                "Parameter {{index}} category": "参数 {{index}} 类别",
                "Safe {index} placeholder": "安全的 {index} 占位符",
                "Source placeholder {{value}}": "普通译文",
                "Translation placeholder": "译文 {{value}}",
            },
        }

        strip_desk_boot_jinja_messages(bootinfo=bootinfo)

        self.assertEqual(
            bootinfo,
            {
                "assets_json": {},
                "__messages": {
                    "Save": "保存",
                    "Safe {index} placeholder": "安全的 {index} 占位符",
                },
            },
        )

    def test_missing_message_catalog_is_unchanged(self) -> None:
        bootinfo = {"assets_json": {}}

        strip_desk_boot_jinja_messages(bootinfo=bootinfo)

        self.assertEqual(bootinfo, {"assets_json": {}})


if __name__ == "__main__":
    unittest.main()

import unittest

from isdt_monitor.parser import FrameError, extract_reading_hex, parse_reading_hex


FRAMES = {
    "channel4": (
        "0224aa2120df040307011916630406d100be004901410019000000be01000000"
        "f09b0600004ef20613082f1c8200000000000000000000000000000000000000"
    ),
    "channel5_first": (
        "0224aa2120df050307011916639205e000fc0049013f00190000009d01000000"
        "f0ab06000016f20613082f1c8200000000000000000000000000000000000000"
    ),
    "channel5_second": (
        "0224aa2120df050307011916639605de00fc00460146001c000000ce01000000"
        "f09306000038f20613082f1c8200000000000000000000000000000000000000"
    ),
    "channel6": (
        "0224aa2120df060307011916639005e100b3004b013d00180000009f01000000"
        "f0a4060000c7f20613082f1c8200000000000000000000000000000000000000"
    ),
    "channel7": (
        "0224aa2120df070307011916630106d800bd0055013d0017000000a101000000"
        "f0a706000049f20613082f1c8200000000000000000000000000000000000000"
    ),
    "channel8_empty": (
        "0224aa2120df0800000000000000000000000000000000000000000000000000"
        "000000000028f20613082f1c8200000000000000000000000000000000000000"
    ),
}


class ParserTests(unittest.TestCase):
    def assert_fields(self, frame_name, expected):
        result = parse_reading_hex(FRAMES[frame_name])
        actual = (
            result.voltage_mv,
            result.current_ma_unverified,
            result.resistance_mohm_unverified,
            result.temperature_c_unverified,
            result.unknown_a,
            result.unknown_b,
            result.unknown_c,
        )
        self.assertEqual(actual, expected)

    def test_channel_4_offsets(self):
        self.assert_fields("channel4", (1540, 209, 190, 32.9, 65, 25, 446))

    def test_channel_5_first_offsets(self):
        self.assert_fields("channel5_first", (1426, 224, 252, 32.9, 63, 25, 413))

    def test_channel_5_second_offsets(self):
        self.assert_fields("channel5_second", (1430, 222, 252, 32.6, 70, 28, 462))

    def test_channel_6_and_7_offsets(self):
        self.assert_fields("channel6", (1424, 225, 179, 33.1, 61, 24, 415))
        self.assert_fields("channel7", (1537, 216, 189, 34.1, 61, 23, 417))

    def test_empty_channel_fields_are_zero(self):
        result = parse_reading_hex(FRAMES["channel8_empty"])
        self.assertEqual(result.frame_channel, 8)
        self.assertFalse(result.has_nonzero_measurement)

    def test_extracts_reading_not_writing_and_uses_last_reading(self):
        output = "Writing deadbeef\nReading aa\nReading " + FRAMES["channel4"] + "\n[]"
        self.assertEqual(extract_reading_hex(output), FRAMES["channel4"])

    def test_rejects_missing_or_short_frame(self):
        with self.assertRaises(FrameError):
            extract_reading_hex("Writing deadbeef")
        with self.assertRaises(FrameError):
            parse_reading_hex("02aa")


if __name__ == "__main__":
    unittest.main()

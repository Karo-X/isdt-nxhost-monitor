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
    "live_channel4": (
        "0224aa2120df04040701191701e1050000a6000000de0054000000d005000000"
        "f09b06000085aca013082f1c8200000000000000000000000000000000000000"
    ),
    "live_channel5": (
        "0224aa2120df05030701191763f8059801b100900262018c0000008407000000"
        "f09c060000a8aca013082f1c8200000000000000000000000000000000000000"
    ),
    "live_channel6_stuffed": (
        "0225aa2120df060307011a1763aaaa05b201e400980267018d0000008407000000"
        "f09c060000b7a013082f1c820000000000000000000000000000000000000000"
    ),
    "live_channel7": (
        "0224aa2120df070407011a1705dd050000b0000000d50052000000a105000000"
        "f09c0600005ab7a013082f1c8200000000000000000000000000000000000000"
    ),
    "live_channel7_nimh_analysis": (
        "0224aa2120df070b09011a1763e105ce00d8003e010300010000001b00000000"
        "f08e0600003e43a013082f1c8200000000000000000000000000000000000000"
    ),
}


class ParserTests(unittest.TestCase):
    def assert_fields(self, frame_name, expected):
        result = parse_reading_hex(FRAMES[frame_name])
        actual = (
            result.temperature_c_candidate,
            result.state_or_soc_candidate,
            result.voltage_mv,
            result.current_ma_unverified,
            result.resistance_mohm_unverified,
            result.unknown_offset19_u16,
            result.unknown_a,
            result.capacity_mah_candidate,
            result.elapsed_seconds_candidate,
        )
        self.assertEqual(actual, expected)

    def test_channel_4_offsets(self):
        self.assert_fields("channel4", (25, 99, 1540, 209, 190, 329, 65, 25, 446))

    def test_channel_5_first_offsets(self):
        self.assert_fields("channel5_first", (25, 99, 1426, 224, 252, 329, 63, 25, 413))

    def test_channel_5_second_offsets(self):
        self.assert_fields("channel5_second", (25, 99, 1430, 222, 252, 326, 70, 28, 462))

    def test_channel_6_and_7_offsets(self):
        self.assert_fields("channel6", (25, 99, 1424, 225, 179, 331, 61, 24, 415))
        self.assert_fields("channel7", (25, 99, 1537, 216, 189, 341, 61, 23, 417))

    def test_live_display_matched_frames(self):
        self.assert_fields("live_channel4", (25, 1, 1505, 0, 166, 0, 222, 84, 1488))
        self.assert_fields("live_channel5", (25, 99, 1528, 408, 177, 656, 354, 140, 1924))
        self.assert_fields("live_channel6_stuffed", (26, 99, 1450, 434, 228, 664, 359, 141, 1924))
        self.assert_fields("live_channel7", (26, 5, 1501, 0, 176, 0, 213, 82, 1441))
        self.assert_fields("live_channel7_nimh_analysis", (26, 99, 1505, 206, 216, 318, 3, 1, 27))

    def test_profile_and_mode_change_is_preserved_as_raw_codes(self):
        before = parse_reading_hex(FRAMES["live_channel7"])
        after = parse_reading_hex(FRAMES["live_channel7_nimh_analysis"])
        self.assertEqual(
            (before.code_7_candidate, before.code_8_candidate, before.code_9_candidate, before.code_11_candidate),
            (4, 7, 1, 23),
        )
        self.assertEqual(
            (after.code_7_candidate, after.code_8_candidate, after.code_9_candidate, after.code_11_candidate),
            (11, 9, 1, 23),
        )

    def test_byte_stuffing_is_removed_before_offsets_are_read(self):
        raw = FRAMES["live_channel6_stuffed"]
        self.assertEqual(len(bytes.fromhex(raw)), 65)
        result = parse_reading_hex(raw)
        self.assertEqual(result.raw_frame, raw)
        self.assertEqual(result.voltage_mv, 1450)

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

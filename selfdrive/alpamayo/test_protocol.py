import unittest

import numpy as np

from selfdrive.alpamayo.protocol import decode_payload, encode_payload, parse_xyzt_dict, serialize_nv12_frame, xyzt_to_dict


class TestAlpamayoProtocol(unittest.TestCase):
  def test_payload_roundtrip(self):
    payload = {
      "protocolVersion": 1,
      "camera": {"deviceType": "tici"},
      "values": [1, 2, 3],
    }

    self.assertEqual(decode_payload(encode_payload(payload)), payload)

  def test_xyzt_roundtrip(self):
    t = np.array([0.0, 0.5, 1.0], dtype=np.float32)
    values = np.array([
      [1.0, 2.0, 3.0],
      [4.0, 5.0, 6.0],
      [7.0, 8.0, 9.0],
    ], dtype=np.float32)

    parsed = parse_xyzt_dict(xyzt_to_dict(t, values), t)
    self.assertIsNotNone(parsed)
    parsed_t, parsed_values = parsed
    np.testing.assert_allclose(parsed_t, t)
    np.testing.assert_allclose(parsed_values, values)

  def test_xyzt_rejects_invalid_shapes(self):
    self.assertIsNone(parse_xyzt_dict({"t": [0.0, 0.5], "x": [1.0], "y": [2.0], "z": [3.0]}, [0.0, 0.5]))
    self.assertIsNone(parse_xyzt_dict({"t": [0.5, 0.0], "x": [1.0, 2.0], "y": [3.0, 4.0], "z": [5.0, 6.0]}, [0.0, 0.5]))

  def test_frame_serialization(self):
    frame = serialize_nv12_frame(
      "road",
      b"\x01\x02\x03\x04",
      width=2,
      height=2,
      stride=2,
      uv_offset=2,
      frame_id=7,
      timestamp_sof=100,
      timestamp_eof=120,
    )

    self.assertEqual(frame["stream"], "road")
    self.assertEqual(frame["encoding"], "nv12")
    self.assertEqual(frame["width"], 2)
    self.assertEqual(frame["frameId"], 7)
    self.assertEqual(frame["timestampEof"], 120)
    self.assertTrue(frame["dataBase64"])


if __name__ == "__main__":
  unittest.main()

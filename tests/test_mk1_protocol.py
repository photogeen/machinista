import unittest
from app.mk1_protocol import *

class Mk1ProtocolTests(unittest.TestCase):
    def test_frame_size_and_pixel_packing(self):
        image=bytearray(255*64)
        self.assertEqual(pack_frame(image),bytes([255])*10880)
        image=bytearray([1])*(255*64)
        self.assertEqual(pack_frame(image),bytes([0,32])*5440)
        image=bytearray(255*64);image[0]=1
        self.assertEqual(pack_frame(image)[:2],bytes((7,255)))
    def test_full_frame_transfer_without_truncation(self):
        data=bytes(i%256 for i in range(10880))
        for display in (0,1):
            packets=list(frame_packets(display,data))
            self.assertEqual(len(packets),24)
            self.assertEqual(packets[0][0],display*2)
            self.assertEqual(packets[2][:4],bytes((display*2,1,247,92)))
            self.assertEqual(packets[2][4:]+b''.join(p[3:] for p in packets[3:]),data)
            self.assertTrue(all(len(p)<=512 for p in packets))
    def test_buttons_include_shift_play_and_all_groups(self):
        self.assertEqual(buttons(bytes((4,255,255,255,255,255,255))),set(BUTTONS)-{None})
        self.assertEqual(buttons(bytes((4,0,8,0,0,0,0))),{'SHIFT'})
    def test_led_order_and_backlight(self):
        a,b=led_packets({'PAD 1':80,'BACKLIGHT':92,'PLAY':255})
        self.assertEqual(len(a),33);self.assertEqual(len(b),33)
        self.assertEqual(a[5],80);self.assertEqual(a[31],255)
        self.assertEqual(b[29],92)
        self.assertEqual(len(LED_NAMES),62)
    def test_pad_words_are_little_endian_without_prefix(self):
        words=[((i%16)<<12)|(i*17) for i in range(32)]
        report=b''.join(w.to_bytes(2,'little') for w in words)
        self.assertEqual(pad_samples(report),tuple((i%16,i*17) for i in range(32)))
        with self.assertRaises(ValueError):pad_samples(report[1:])
    def test_pad_mode_is_a_button_not_a_pad(self):
        self.assertFalse(is_pad_led('PAD MODE'))
        self.assertTrue(all(is_pad_led(f'PAD {i}') for i in range(1,17)))
        self.assertFalse(is_pad_led('PAD 17'))
    def test_reject_invalid_frames_and_leds(self):
        with self.assertRaises(ValueError):list(frame_packets(2,b''))
        with self.assertRaises(ValueError):pack_frame(bytearray(256*64))
        with self.assertRaises(ValueError):led_packets({'PLAY':256})
        with self.assertRaises(ValueError):led_packets({'UNKNOWN':1})
if __name__=='__main__':unittest.main()

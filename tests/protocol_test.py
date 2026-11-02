"""Exercise the handshake against a frozen response from the original driver."""

import ctypes as C
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VECTOR = json.loads((ROOT / "tests/handshake.json").read_text())


class Context(C.Structure):
    _fields_ = [("tick_multiplier", C.c_uint32), ("tick_count", C.c_uint64),
                ("cookie", C.c_uint32), ("process_id", C.c_uint64),
                ("process_peb", C.c_uint64)]


class ProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = C.CDLL(str(ROOT / "build/protocol.so"))
        cls.library.randgrid_protocol_derive.argtypes = [C.POINTER(Context), C.c_uint64,
                                                        C.c_void_p, C.c_void_p]
        cls.library.randgrid_protocol_derive.restype = None
        cls.library.randgrid_protocol_request.argtypes = [C.POINTER(Context), C.c_void_p,
            C.c_size_t, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        cls.library.randgrid_protocol_request.restype = C.c_uint32
        cls.library.crypto_aead_encrypt.argtypes = [C.c_void_p, C.POINTER(C.c_ulonglong),
            C.c_void_p, C.c_ulonglong, C.c_void_p, C.c_ulonglong, C.c_void_p, C.c_void_p, C.c_void_p]
        cls.library.crypto_aead_encrypt.restype = C.c_int

    def setUp(self):
        self.context = Context(**VECTOR["context"])
        self.request = bytes.fromhex(VECTOR["request"])
        self.response = bytes.fromhex(VECTOR["response"])
        self.ticks = self.context.tick_multiplier * (self.context.tick_count & 0xffffffff) >> 24
        self.bucket = (self.ticks + 1023) & ~1023

    def derive(self, bucket):
        key, nonce = C.create_string_buffer(16), C.create_string_buffer(16)
        self.library.randgrid_protocol_derive(C.byref(self.context), bucket, key, nonce)
        return key, nonce

    def encrypt(self, plaintext, bucket):
        key, nonce = self.derive(bucket)
        packet = C.create_string_buffer(len(plaintext) + 16)
        count = C.c_ulonglong()
        self.assertEqual(self.library.crypto_aead_encrypt(packet, C.byref(count), plaintext,
            len(plaintext), None, 0, None, nonce, key), 0)
        return packet.raw[:count.value]

    def check_reply(self, payload, capacity, status, response, alias=False):
        storage = C.create_string_buffer(bytes([0xa5]) * 160, 160)
        if alias:
            C.memmove(storage, payload, len(payload))
            source = storage
        else:
            source = C.create_string_buffer(payload)
        returned = C.c_size_t(999)
        actual = self.library.randgrid_protocol_request(C.byref(self.context), source,
            len(payload), storage, capacity, C.byref(returned))
        self.assertEqual(actual, status)
        self.assertEqual(returned.value, len(response))
        self.assertEqual(storage.raw[:returned.value], response)
        if not alias:
            self.assertEqual(storage.raw[capacity:], bytes([0xa5]) * (160 - capacity))

    def test_original_response_and_alias(self):
        key, nonce = self.derive(self.bucket)
        self.assertEqual(key.raw.hex(), VECTOR["key"])
        self.assertEqual(nonce.raw.hex(), VECTOR["nonce"])
        for alias in (False, True):
            with self.subTest(alias=alias):
                self.check_reply(self.request, 144, 0x20000000, self.response, alias=alias)

    def test_original_capacity_behavior(self):
        for capacity in (0, 15, 16, 23, 24):
            with self.subTest(capacity=capacity):
                self.check_reply(self.request, capacity,
                    0xe0000001 if capacity < 16 else 0x20000000,
                    self.response if capacity >= 24 else b"")

    def test_authentication(self):
        mutated = bytes([self.request[0] ^ 1]) + self.request[1:]
        self.check_reply(mutated, 144, 0xe0000001, b"")

    def test_previous_bucket(self):
        plaintext = bytes.fromhex("703a31c500000000847cb93ffac93d94")
        packet = self.encrypt(plaintext, self.ticks & ~1023)
        self.check_reply(packet, 144, 0x20000000, self.response)

    def test_unimplemented_command_and_wrong_marker(self):
        plaintext = bytes.fromhex("703a31c500000000847cb93ffac93d94")
        wrong = self.encrypt(plaintext[:8] + bytes(8), self.bucket)
        self.check_reply(wrong, 144, 0xe0000001, b"")
        unknown = self.encrypt(bytes.fromhex("efbeadde") + plaintext[4:], self.bucket)
        self.check_reply(unknown, 144, 0xc0000010, b"")


if __name__ == "__main__":
    unittest.main()

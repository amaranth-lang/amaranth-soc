# amaranth: UnusedElaboratable=no

import unittest
import warnings
from amaranth import *
from amaranth.hdl import UnusedElaboratable
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import *

from amaranth_soc.csr.reg import *
from amaranth_soc.csr import action, Element
from amaranth_soc.memory import MemoryMap


# The `amaranth: UnusedElaboratable=no` modeline isn't enough here.
warnings.simplefilter(action="ignore", category=UnusedElaboratable)


def _compatible_fields(a, b):
    return a.port.shape == b.port.shape and a.port.access == b.port.access


class FieldPortSignatureTestCase(unittest.TestCase):
    def test_shape_1_ro(self):
        sig = FieldPort.Signature(1, "r")
        self.assertEqual(sig.shape, unsigned(1))
        self.assertEqual(sig.access, FieldPort.Access.R)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(unsigned(1)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(1)),
            "w_stb":  Out(1),
        }).members)
        self.assertEqual(repr(sig),
                         "csr.FieldPort.Signature(SignatureMembers({"
                             "'r_data': In(unsigned(1)), "
                             "'r_stb': Out(1), "
                             "'w_data': Out(unsigned(1)), "
                             "'w_stb': Out(1)}))")

    def test_shape_8_rw(self):
        sig = FieldPort.Signature(8, "rw")
        self.assertEqual(sig.shape, unsigned(8))
        self.assertEqual(sig.access, FieldPort.Access.RW)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(unsigned(8)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(8)),
            "w_stb":  Out(1),
        }).members)

    def test_shape_10_wo(self):
        sig = FieldPort.Signature(10, "w")
        self.assertEqual(sig.shape, unsigned(10))
        self.assertEqual(sig.access, FieldPort.Access.W)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(unsigned(10)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(10)),
            "w_stb":  Out(1),
        }).members)

    def test_shape_0_rw(self):
        sig = FieldPort.Signature(0, "w")
        self.assertEqual(sig.shape, unsigned(0))
        self.assertEqual(sig.access, FieldPort.Access.W)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(unsigned(0)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(0)),
            "w_stb":  Out(1),
        }).members)

    def test_shape_8_nc(self):
        sig = FieldPort.Signature(8, "nc")
        self.assertEqual(sig.shape, unsigned(8))
        self.assertEqual(sig.access, FieldPort.Access.NC)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(unsigned(8)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(8)),
            "w_stb":  Out(1),
        }).members)

    def test_create(self):
        sig  = FieldPort.Signature(unsigned(8), "rw")
        port = sig.create(path=("foo", "bar"))
        self.assertIsInstance(port, FieldPort)
        self.assertEqual(port.shape, unsigned(8))
        self.assertEqual(port.access, FieldPort.Access.RW)
        self.assertEqual(port.r_stb.name, "foo__bar__r_stb")
        self.assertIs(port.signature, sig)

    def test_eq(self):
        self.assertEqual(FieldPort.Signature(8, "r"), FieldPort.Signature(8, "r"))
        self.assertEqual(FieldPort.Signature(8, "r"), FieldPort.Signature(8, FieldPort.Access.R))
        # different shape
        self.assertNotEqual(FieldPort.Signature(8, "r"), FieldPort.Signature(1, "r"))
        # different access mode
        self.assertNotEqual(FieldPort.Signature(8, "r"), FieldPort.Signature(8, "w"))
        self.assertNotEqual(FieldPort.Signature(8, "r"), FieldPort.Signature(8, "rw"))
        self.assertNotEqual(FieldPort.Signature(8, "w"), FieldPort.Signature(8, "rw"))

    def test_wrong_shape(self):
        with self.assertRaisesRegex(TypeError,
                r"Field shape must be a shape-like object, not 'foo'"):
            port = FieldPort.Signature("foo", "rw")

    def test_wrong_access(self):
        with self.assertRaisesRegex(ValueError, r"'wo' is not a valid FieldPort.Access"):
            port = FieldPort.Signature(8, "wo")


class FieldPortTestCase(unittest.TestCase):
    def test_simple(self):
        sig  = FieldPort.Signature(unsigned(8), "rw")
        port = FieldPort(sig, path=("foo", "bar"))
        self.assertEqual(port.shape, unsigned(8))
        self.assertEqual(port.access, FieldPort.Access.RW)
        self.assertEqual(port.r_stb.name, "foo__bar__r_stb")
        self.assertIs(port.signature, sig)
        self.assertEqual(repr(port),
                         "csr.FieldPort(csr.FieldPort.Signature(SignatureMembers({"
                             "'r_data': In(unsigned(8)), "
                             "'r_stb': Out(1), "
                             "'w_data': Out(unsigned(8)), "
                             "'w_stb': Out(1)})))")

    def test_wrong_signature(self):
        with self.assertRaisesRegex(TypeError,
                r"This interface requires a csr\.FieldPort\.Signature, not 'foo'"):
            FieldPort("foo")


class FieldTestCase(unittest.TestCase):
    def test_wrong_class(self):
        class Foo:
            pass
        with self.assertRaisesRegex(TypeError,
                r"Foo must be a subclass of csr\.FieldAction"):
            Field(Foo)

    def test_create(self):
        class MockAction(FieldAction):
            def __init__(self, shape, *, init):
                super().__init__(shape, access="rw", members={
                    "data": Out(shape)
                })
                self.init = init

            def elaborate(self, platform):
                return Module()

        field_u8 = Field(MockAction, unsigned(8), init=1).create()
        self.assertEqual(field_u8.port.shape, unsigned(8))
        self.assertEqual(field_u8.init, 1)

    def test_create_multiple(self):
        class MockAction(FieldAction):
            def __init__(self):
                super().__init__(unsigned(8), access="rw")

            def elaborate(self, platform):
                return Module()

        field_1 = Field(MockAction).create()
        field_2 = Field(MockAction).create()
        self.assertIsNot(field_1, field_2)


class FieldActionTestCase(unittest.TestCase):
    def test_simple(self):
        field = FieldAction(unsigned(8), access="rw", members={"foo": Out(unsigned(1))})
        self.assertEqual(field.signature, wiring.Signature({
            "port": In(FieldPort.Signature(unsigned(8), "rw")),
            "foo": Out(unsigned(1))
        }))

    def test_port_name(self):
        with self.assertRaisesRegex(ValueError,
                r"'port' is a reserved name, which must not be assigned to member "
                r"Out\(unsigned\(1\)\)"):
            FieldAction(unsigned(8), access="rw", members={"port": Out(unsigned(1))})

class FieldActionMapTestCase(unittest.TestCase):
    def test_simple(self):
        field_map = FieldActionMap({
            "a": Field(action.R, unsigned(1)),
            "b": Field(action.RW, signed(3)),
            "c": {"d": Field(action.RW, unsigned(4))},
        })

        field_r_u1  = Field(action.R, unsigned(1)).create()
        field_rw_s3 = Field(action.RW, signed(3)).create()
        field_rw_u4 = Field(action.RW, unsigned(4)).create()

        self.assertTrue(_compatible_fields(field_map["a"], field_r_u1))
        self.assertTrue(_compatible_fields(field_map["b"], field_rw_s3))
        self.assertTrue(_compatible_fields(field_map["c"]["d"], field_rw_u4))

        self.assertTrue(_compatible_fields(field_map.a, field_r_u1))
        self.assertTrue(_compatible_fields(field_map.b, field_rw_s3))
        self.assertTrue(_compatible_fields(field_map.c.d, field_rw_u4))

        self.assertEqual(len(field_map), 3)

    def test_iter(self):
        field_map = FieldActionMap({
            "a": Field(action.R, unsigned(1)),
            "b": Field(action.RW, signed(3))
        })
        self.assertEqual(list(field_map.items()), [
            ("a", field_map["a"]),
            ("b", field_map["b"]),
        ])

    def test_flatten(self):
        field_map = FieldActionMap({
            "a": Field(action.R, unsigned(1)),
            "b": Field(action.RW, signed(3)),
            "c": {"d": Field(action.RW, unsigned(4))},
        })
        self.assertEqual(list(field_map.flatten()), [
            (("a",), field_map["a"]),
            (("b",), field_map["b"]),
            (("c", "d"), field_map["c"]["d"]),
        ])

    def test_wrong_dict(self):
        with self.assertRaisesRegex(TypeError,
                r"Fields must be provided as a non-empty dict, not 'foo'"):
            FieldActionMap("foo")

    def test_wrong_field_key(self):
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not 1"):
            FieldActionMap({1: Field(action.RW, unsigned(1))})
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not ''"):
            FieldActionMap({"": Field(action.RW, unsigned(1))})

    def test_wrong_field_value(self):
        with self.assertRaisesRegex(TypeError,
                r"unsigned\(1\) must either be a Field object, a dict or a list of Field objects"):
            FieldActionMap({"a": unsigned(1)})

    def test_getitem_wrong_key(self):
        field_map = FieldActionMap({"a": Field(action.RW, unsigned(1))})
        with self.assertRaises(KeyError):
            field_map["b"]

    def test_getitem_reserved(self):
        field_map = FieldActionMap({"_reserved": Field(action.RW, unsigned(1))})
        field_rw_u1 = Field(action.RW, unsigned(1)).create()
        self.assertTrue(_compatible_fields(field_map["_reserved"], field_rw_u1))

    def test_getattr_missing(self):
        field_map = FieldActionMap({"a": Field(action.RW, unsigned(1)),
                              "b": Field(action.RW, unsigned(1))})
        with self.assertRaisesRegex(AttributeError,
                r"Field map does not have a field 'c'; did you mean one of: 'a', 'b'?"):
            field_map.c

    def test_getattr_reserved(self):
        field_map = FieldActionMap({"_reserved": Field(action.RW, unsigned(1))})
        with self.assertRaisesRegex(AttributeError,
                r"Field map field '_reserved' has a reserved name and may only be accessed by "
                r"indexing"):
            field_map._reserved


class FieldActionArrayTestCase(unittest.TestCase):
    def test_simple(self):
        field_array = FieldActionArray([Field(action.RW, unsigned(2)) for _ in range(8)])
        field_rw_u2 = Field(action.RW, unsigned(2)).create()
        self.assertEqual(len(field_array), 8)
        for i in range(8):
            self.assertTrue(_compatible_fields(field_array[i], field_rw_u2))

    def test_dim_2(self):
        field_array = FieldActionArray([[Field(action.RW, unsigned(1)) for _ in range(4)]
                                  for _ in range(4)])
        field_rw_u1 = Field(action.RW, unsigned(1)).create()
        self.assertEqual(len(field_array), 4)
        for i in range(4):
            for j in range(4):
                self.assertTrue(_compatible_fields(field_array[i][j], field_rw_u1))

    def test_nested(self):
        field_array = FieldActionArray([{"a": Field(action.RW, unsigned(4)),
                                   "b": [Field(action.RW, unsigned(1)) for _ in range(4)]}
                                  for _ in range(4)])
        field_rw_u4 = Field(action.RW, unsigned(4)).create()
        field_rw_u1 = Field(action.RW, unsigned(1)).create()
        self.assertEqual(len(field_array), 4)
        for i in range(4):
            self.assertTrue(_compatible_fields(field_array[i]["a"], field_rw_u4))
            for j in range(4):
                self.assertTrue(_compatible_fields(field_array[i]["b"][j], field_rw_u1))

    def test_iter(self):
        field_array = FieldActionArray([Field(action.RW, 1) for _ in range(3)])
        self.assertEqual(list(field_array), [
            field_array[i] for i in range(3)
        ])

    def test_flatten(self):
        field_array = FieldActionArray([{"a": Field(action.RW, 4),
                                   "b": [Field(action.RW, 1) for _ in range(2)]}
                                  for _ in range(2)])
        self.assertEqual(list(field_array.flatten()), [
            ((0, "a"), field_array[0]["a"]),
            ((0, "b", 0), field_array[0]["b"][0]),
            ((0, "b", 1), field_array[0]["b"][1]),
            ((1, "a"), field_array[1]["a"]),
            ((1, "b", 0), field_array[1]["b"][0]),
            ((1, "b", 1), field_array[1]["b"][1]),
        ])

    def test_wrong_fields(self):
        with self.assertRaisesRegex(TypeError,
                r"Fields must be provided as a non-empty list, not 'foo'"):
            FieldActionArray("foo")
        with self.assertRaisesRegex(TypeError,
                r"Fields must be provided as a non-empty list, not \[\]"):
            FieldActionArray([])

    def test_wrong_field(self):
        with self.assertRaisesRegex(TypeError,
                r"'foo' must be a Field object or a collection of Field objects"):
            FieldActionArray(["foo", Field(action.RW, 1)])


class RegisterTestCase(unittest.TestCase):
    def test_annotations(self):
        class FooRegister(Register, access="rw"):
            a: Field(action.R, unsigned(1))
            b: {"c": Field(action.RW1C, unsigned(3)),
                "d": [Field(action.W, unsigned(1)) for _ in range(2)]}
            e: [*({"f": Field(action.RW, signed(2))} for _ in range(2)),
                [Field(action.RW, signed(2))]]
            g: {"x": "foo", "y": dict(), "z": "bar"}
            h: ["foo", [], dict()]

            foo: unsigned(42)

        reg = FooRegister()

        field_r_u1    = Field(action.R,    unsigned(1)).create()
        field_rw1c_u3 = Field(action.RW1C, unsigned(3)).create()
        field_w_u1    = Field(action.W,    unsigned(1)).create()
        field_rw_s2   = Field(action.RW,     signed(2)).create()

        self.assertTrue(_compatible_fields(reg.f.a,       field_r_u1))
        self.assertTrue(_compatible_fields(reg.f.b.c,     field_rw1c_u3))
        self.assertTrue(_compatible_fields(reg.f.b.d[0],  field_w_u1))
        self.assertTrue(_compatible_fields(reg.f.b.d[1],  field_w_u1))
        self.assertTrue(_compatible_fields(reg.f.e[0].f,  field_rw_s2))
        self.assertTrue(_compatible_fields(reg.f.e[1].f,  field_rw_s2))
        self.assertTrue(_compatible_fields(reg.f.e[2][0], field_rw_s2))

        self.assertEqual(reg.element.access, Element.Access.RW)
        self.assertEqual(reg.element.width, 12)

    def test_access_init(self):
        class FooRegister(Register):
            a: Field(action.R, unsigned(1))

        reg = FooRegister(access="r")
        self.assertEqual(reg.element.access, Element.Access.R)

    def test_access_same(self):
        class FooRegister(Register, access="r"):
            a: Field(action.R, unsigned(1))

        reg = FooRegister(access="r")
        self.assertEqual(reg.element.access, Element.Access.R)

    def test_fields_dict(self):
        class FooRegister(Register, access=Element.Access.RW):
            pass

        reg = FooRegister({
            "a": Field(action.R, unsigned(1)),
            "b": Field(action.RW1C, unsigned(3)),
            "c": {"d": Field(action.RW, signed(2))},
            "e": [Field(action.W, unsigned(1)) for _ in range(2)]
        })

        field_r_u1    = Field(action.R,    unsigned(1)).create()
        field_rw1c_u3 = Field(action.RW1C, unsigned(3)).create()
        field_rw_s2   = Field(action.RW,     signed(2)).create()
        field_w_u1    = Field(action.W,    unsigned(1)).create()

        self.assertTrue(_compatible_fields(reg.f.a,    field_r_u1))
        self.assertTrue(_compatible_fields(reg.f.b,    field_rw1c_u3))
        self.assertTrue(_compatible_fields(reg.f.c.d,  field_rw_s2))
        self.assertTrue(_compatible_fields(reg.f.e[0], field_w_u1))
        self.assertTrue(_compatible_fields(reg.f.e[1], field_w_u1))

        self.assertEqual(reg.element.access, Element.Access.RW)
        self.assertEqual(reg.element.width, 8)

    def test_fields_list(self):
        class FooRegister(Register, access="r"):
            pass

        reg = FooRegister([{"a": Field(action.R, unsigned(1))} for _ in range(2)])

        field_r_u1 = Field(action.R, unsigned(1)).create()

        self.assertTrue(_compatible_fields(reg.f[0].a, field_r_u1))
        self.assertTrue(_compatible_fields(reg.f[1].a, field_r_u1))

        self.assertEqual(reg.element.access, Element.Access.R)
        self.assertEqual(reg.element.width, 2)

    def test_fields_single(self):
        reg = Register(Field(action.R, unsigned(1)), access="r")

        field_r_u1 = Field(action.R, unsigned(1)).create()

        self.assertTrue(_compatible_fields(reg.f, field_r_u1))

        self.assertEqual(reg.element.access, Element.Access.R)
        self.assertEqual(reg.element.width, 1)

    def test_wrong_access(self):
        with self.assertRaisesRegex(ValueError, r"'foo' is not a valid Element.Access"):
            Register({"a": Field(action.R, unsigned(1))}, access="foo")
        with self.assertRaisesRegex(ValueError, r"'foo' is not a valid Element.Access"):
            class FooRegister(Register, access="foo"):
                pass

    def test_no_access(self):
        with self.assertRaisesRegex(ValueError,
                r"Element access mode must be provided during class creation or instantiation"):
            Register({"a": Field(action.R, unsigned(1))})

        class FooRegister(Register, access=None):
            pass
        with self.assertRaisesRegex(ValueError,
                r"Element access mode must be provided during class creation or instantiation"):
            FooRegister({"a": Field(action.R, unsigned(1))})

        class BarRegister(Register):
            pass
        with self.assertRaisesRegex(ValueError,
                r"Element access mode must be provided during class creation or instantiation"):
            BarRegister({"a": Field(action.R, unsigned(1))})

    def test_access_conflict(self):
        class FooRegister(Register, access="r"):
            a: Field(action.R, unsigned(1))
        with self.assertRaisesRegex(ValueError,
                r"Element access mode Access\.RW conflicts with the value provided during class "
                r"creation: Access\.R"):
            FooRegister(access="rw")

    def test_wrong_fields(self):
        class FooRegister(Register, access="w"):
            pass
        with self.assertRaisesRegex(TypeError,
                r"Field collection must be a dict, list, or Field, not 'foo'"):
            FooRegister(fields="foo")

    def test_annotations_conflict(self):
        class FooRegister(Register, access="rw"):
            a: Field(action.R, unsigned(1))
        with self.assertRaisesRegex(ValueError,
                r"Field collection \{'b': <.*>\} cannot be provided in addition to field "
                r"annotations: a"):
            FooRegister({"b": Field(action.W, unsigned(1))})

    def test_annotations_other(self):
        class FooRegister(Register, access="rw"):
            foo: "bar"
        reg = FooRegister({"a": Field(action.R, unsigned(1))})
        field_r_u1 = Field(action.R, unsigned(1)).create()
        self.assertTrue(_compatible_fields(reg.f.a, field_r_u1))
        self.assertEqual(reg.element.width, 1)

    def test_access_mismatch(self):
        class WRegister(Register, access="w"):
            pass
        class RRegister(Register, access="r"):
            pass
        with self.assertRaisesRegex(ValueError,
                r"Field a__b is readable, but element access mode is Access\.W"):
            WRegister({"a": {"b": Field(action.RW, unsigned(1))}})
        with self.assertRaisesRegex(ValueError,
                r"Field a__b is writable, but element access mode is Access\.R"):
            RRegister({"a": {"b": Field(action.RW, unsigned(1))}})

    def test_iter(self):
        class FooRegister(Register, access="rw"):
            a: Field(action.R, unsigned(1))
            b: Field(action.RW1C, unsigned(3))
            c: {"d": Field(action.RW, signed(2))}
            e: [Field(action.W, unsigned(1)) for _ in range(2)]

        reg = FooRegister()
        self.assertEqual(list(reg), [
            (("a",), reg.f.a),
            (("b",), reg.f.b),
            (("c", "d"), reg.f.c.d),
            (("e", 0), reg.f.e[0]),
            (("e", 1), reg.f.e[1]),
        ])

    def test_iter_single(self):
        reg = Register(Field(action.R, unsigned(1)), access="rw")
        self.assertEqual(list(reg), [
            ((), reg.f),
        ])

    def test_sim(self):
        class FooRegister(Register, access="rw"):
            a: Field(action.R, unsigned(1))
            b: Field(action.RW1C, unsigned(3), init=0b111)
            c: {"d": Field(action.RW, signed(2), init=-1)}
            e: [Field(action.W, unsigned(1)) for _ in range(2)]
            f: Field(action.RW1S, unsigned(3))

        dut = FooRegister()

        async def testbench(ctx):
            # Check init values:

            self.assertEqual(ctx.get(dut.f.b  .data),  0b111)
            self.assertEqual(ctx.get(dut.f.c.d.data), -1)
            self.assertEqual(ctx.get(dut.f.f  .data),  0b000)

            self.assertEqual(ctx.get(dut.f.b   .port.r_data),  0b111)
            self.assertEqual(ctx.get(dut.f.c.d .port.r_data), -1)
            self.assertEqual(ctx.get(dut.f.f   .port.r_data),  0b000)

            # Initiator read:

            ctx.set(dut.element.r_stb, 1)

            self.assertEqual(ctx.get(dut.f.a.port.r_stb), 1)
            self.assertEqual(ctx.get(dut.f.b.port.r_stb), 1)
            self.assertEqual(ctx.get(dut.f.f.port.r_stb), 1)

            ctx.set(dut.element.r_stb, 0)

            # Initiator write:

            ctx.set(dut.element.w_stb, 1)
            ctx.set(dut.element.w_data, Cat(
                Const(0b1,   1), # a
                Const(0b010, 3), # b
                Const(0b00,  2), # c.d
                Const(0b00,  2), # e
                Const(0b110, 3), # f
            ))

            self.assertEqual(ctx.get(dut.f.a   .port.w_stb), 0)
            self.assertEqual(ctx.get(dut.f.b   .port.w_stb), 1)
            self.assertEqual(ctx.get(dut.f.c.d .port.w_stb), 1)
            self.assertEqual(ctx.get(dut.f.e[0].port.w_stb), 1)
            self.assertEqual(ctx.get(dut.f.e[1].port.w_stb), 1)
            self.assertEqual(ctx.get(dut.f.f   .port.w_stb), 1)

            self.assertEqual(ctx.get(dut.f.b   .port.w_data), 0b010)
            self.assertEqual(ctx.get(dut.f.c.d .port.w_data), 0b00)
            self.assertEqual(ctx.get(dut.f.e[0].port.w_data), 0b0)
            self.assertEqual(ctx.get(dut.f.e[1].port.w_data), 0b0)
            self.assertEqual(ctx.get(dut.f.f   .port.w_data), 0b110)

            self.assertEqual(ctx.get(dut.f.e[0].w_data), 0b0)
            self.assertEqual(ctx.get(dut.f.e[1].w_data), 0b0)

            await ctx.tick()
            ctx.set(dut.element.w_stb, 0)

            self.assertEqual(ctx.get(dut.f.b  .data), 0b101)
            self.assertEqual(ctx.get(dut.f.c.d.data), 0b00)
            self.assertEqual(ctx.get(dut.f.f  .data), 0b110)

            # User write:

            ctx.set(dut.f.a.r_data, 0b1)
            ctx.set(dut.f.b.set,    0b010)
            ctx.set(dut.f.f.clear,  0b010)

            self.assertEqual(ctx.get(dut.element.r_data),
                             Const.cast(Cat(
                                 Const(0b1,   1), # a
                                 Const(0b101, 3), # b
                                 Const(0b00,  2), # c.d
                                 Const(0b00,  2), # e
                                 Const(0b110, 3), # f
                             )).value)

            await ctx.tick()
            ctx.set(dut.f.a.r_data, 0b0)
            ctx.set(dut.f.b.set,    0b000)
            ctx.set(dut.f.f.clear,  0b000)

            self.assertEqual(ctx.get(dut.element.r_data),
                             Const.cast(Cat(
                                 Const(0b0,   1), # a
                                 Const(0b111, 3), # b
                                 Const(0b00,  2), # c.d
                                 Const(0b00,  2), # e
                                 Const(0b100, 3), # f
                             )).value)

            # Concurrent writes:

            ctx.set(dut.element.w_stb, 1)
            ctx.set(dut.element.w_data, Cat(
                Const(0b0,   1), # a
                Const(0b111, 3), # b
                Const(0b00,  2), # c.d
                Const(0b00,  2), # e
                Const(0b111, 3), # f
            ))

            ctx.set(dut.f.b.set,   0b001)
            ctx.set(dut.f.f.clear, 0b111)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.element.r_data),
                             Const.cast(Cat(
                                 Const(0b0,   1), # a
                                 Const(0b001, 3), # b
                                 Const(0b00,  2), # c.d
                                 Const(0b00,  2), # e
                                 Const(0b111, 3), # f
                             )).value)

            self.assertEqual(ctx.get(dut.f.b.data), 0b001)
            self.assertEqual(ctx.get(dut.f.f.data), 0b111)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_sim_single(self):
        dut = Register(Field(action.RW, unsigned(1), init=1), access="rw")

        async def testbench(ctx):
            # Check init values:

            self.assertEqual(ctx.get(dut.f.data), 1)
            self.assertEqual(ctx.get(dut.f.port.r_data), 1)

            # Initiator read:

            ctx.set(dut.element.r_stb, 1)
            self.assertEqual(ctx.get(dut.f.port.r_stb), 1)
            ctx.set(dut.element.r_stb, 0)

            # Initiator write:

            ctx.set(dut.element.w_stb, 1)
            ctx.set(dut.element.w_data, 0)

            self.assertEqual(ctx.get(dut.f.port.w_stb), 1)
            self.assertEqual(ctx.get(dut.f.port.w_data), 0)

            await ctx.tick()
            ctx.set(dut.element.w_stb, 0)
            self.assertEqual(ctx.get(dut.f.data), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

class _MockRegister(Register, access="rw"):
    def __init__(self, name, width=1):
        super().__init__({"a": Field(action.RW, unsigned(width))})
        self._name = name

    def __repr__(self):
        return f"_MockRegister({self._name!r})"


class BuilderTestCase(unittest.TestCase):
    def test_init(self):
        # default granularity
        regs_0 = Builder(addr_width=30, data_width=32)
        self.assertEqual(regs_0.addr_width, 30)
        self.assertEqual(regs_0.data_width, 32)
        self.assertEqual(regs_0.granularity, 8)
        # custom granularity
        regs_1 = Builder(addr_width=31, data_width=32, granularity=16)
        self.assertEqual(regs_1.addr_width, 31)
        self.assertEqual(regs_1.data_width, 32)
        self.assertEqual(regs_1.granularity, 16)

    def test_init_wrong_addr_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Address width must be a positive integer, not 'foo'"):
            Builder(addr_width="foo", data_width=32)

    def test_init_wrong_data_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Data width must be a positive integer, not 'foo'"):
            Builder(addr_width=30, data_width="foo")

    def test_init_wrong_granularity(self):
        with self.assertRaisesRegex(TypeError,
                r"Granularity must be a positive integer, not 'foo'"):
            Builder(addr_width=30, data_width=32, granularity="foo")

    def test_init_granularity_divisor(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity 7 is not a divisor of data width 32"):
            Builder(addr_width=30, data_width=32, granularity=7)

    def test_add(self):
        regs = Builder(addr_width=30, data_width=32)
        ra = regs.add("a", _MockRegister("a"))
        rb = regs.add("b", _MockRegister("b"), offset=4)
        self.assertEqual(list(regs._registers.values()), [
            (ra, ('a',), None),
            (rb, ('b',), 4),
        ])

    def test_add_cluster(self):
        regs = Builder(addr_width=30, data_width=32)
        with regs.Cluster("a"):
            rb = regs.add("b", _MockRegister("b"))
        rc = regs.add("c", _MockRegister("c"))
        self.assertEqual(list(regs._registers.values()), [
            (rb, ('a', 'b'), None),
            (rc, ('c',),     None),
        ])

    def test_add_array(self):
        regs = Builder(addr_width=30, data_width=32)
        with regs.Index(10):
            ra = regs.add("a", _MockRegister("a"))
        rb = regs.add("b", _MockRegister("b"))
        self.assertEqual(list(regs._registers.values()), [
            (ra, (10, 'a'), None),
            (rb, ('b',),    None),
        ])

    def test_add_nested(self):
        # cluster -> cluster & index
        regs_0 = Builder(addr_width=30, data_width=32)
        with regs_0.Cluster("foo"):
            with regs_0.Cluster("bar"):
                ra = regs_0.add("a", _MockRegister("a"))
            with regs_0.Index(10):
                rb = regs_0.add("b", _MockRegister("b"))
            rc = regs_0.add("c", _MockRegister("c"))
        self.assertEqual(list(regs_0._registers.values()), [
            (ra, ("foo", "bar", "a"), None),
            (rb, ("foo", 10, "b"),    None),
            (rc, ("foo", "c"),        None),
        ])
        # index -> index & cluster
        regs_1 = Builder(addr_width=8, data_width=8)
        with regs_1.Index(3):
            with regs_1.Index(7):
                rd = regs_1.add("d", _MockRegister("d"))
                re = regs_1.add("e", _MockRegister("e"))
            with regs_1.Cluster("foo"):
                rf = regs_1.add("f", _MockRegister("f"))

    def test_add_wrong_reg(self):
        regs = Builder(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Register must be an instance of csr\.Register, not 'bar'"):
            regs.add("foo", "bar")

    def test_add_frozen(self):
        regs = Builder(addr_width=8, data_width=8)
        regs.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Builder is frozen. Cannot add register _MockRegister\('a'\)"):
            regs.add("a", _MockRegister("a"))

    def test_add_wrong_name(self):
        regs = Builder(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Register name must be a non-empty string, not 1"):
            regs.add(1, _MockRegister("a"))
        with self.assertRaisesRegex(TypeError,
                r"Register name must be a non-empty string, not ''"):
            regs.add('', _MockRegister("a"))
        with self.assertRaisesRegex(TypeError,
                r"Register name must be a non-empty string, not \(\)"):
            regs.add((), _MockRegister("a"))

    def test_add_wrong_offset(self):
        regs = Builder(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Offset must be a non-negative integer, not 'foo'"):
            regs.add("a", _MockRegister("a"), offset="foo")
        with self.assertRaisesRegex(TypeError,
                r"Offset must be a non-negative integer, not -1"):
            regs.add("a", _MockRegister("a"), offset=-1)

    def test_add_misaligned_offset(self):
        regs = Builder(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError, r"Offset 0x1 must be a multiple of 0x4 bytes"):
            regs.add("a", _MockRegister("a"), offset=1)

    def test_add_twice(self):
        regs = Builder(addr_width=8, data_width=8)
        ra = regs.add("a", _MockRegister("a"))
        rb = regs.add("b", _MockRegister("b"), offset=1)
        with self.assertRaisesRegex(ValueError,
                r"Register _MockRegister\('a'\) is already added with name \('a',\) at an "
                r"implicit offset"):
            regs.add("aa", ra)
        with self.assertRaisesRegex(ValueError,
                r"Register _MockRegister\('b'\) is already added with name \('b',\) at an "
                r"explicit offset 0x1"):
            regs.add("bb", rb)

    def test_cluster_wrong_name(self):
        regs = Builder(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Cluster name must be a non-empty string, not -1"):
            with regs.Cluster(-1):
                pass
        with self.assertRaisesRegex(TypeError,
                r"Cluster name must be a non-empty string, not ''"):
            with regs.Cluster(""):
                pass
        with self.assertRaisesRegex(TypeError,
                r"Cluster name must be a non-empty string, not \(\)"):
            with regs.Cluster(()):
                pass

    def test_array_wrong_index(self):
        regs = Builder(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Array index must be a non-negative integer, not 'foo'"):
            with regs.Index("foo"):
                pass
        with self.assertRaisesRegex(TypeError,
                r"Array index must be a non-negative integer, not -1"):
            with regs.Index(-1):
                pass

    def test_memory_map(self):
        regs = Builder(addr_width=30, data_width=32)
        ra = regs.add("a", _MockRegister("ra")) # offset=0x0
        with regs.Cluster("b"):
            rc = regs.add("c", _MockRegister("rc"), offset=0xc)
            rd = regs.add("d", _MockRegister("rd"), offset=0x4)
            re = regs.add("e", _MockRegister("re")) # offset=0x8
            with regs.Index(0):
                rf = regs.add("f", _MockRegister("rf", width=32), offset=0x10)
            with regs.Index(1):
                rg = regs.add("g", _MockRegister("rg", width=48)) # offset=0x18

        memory_map = regs.as_memory_map()
        self.assertEqual(memory_map.addr_width, 30)
        self.assertEqual(memory_map.data_width, 32)
        self.assertEqual(memory_map.alignment, 0)

        self.assertFalse(list(memory_map.windows()))

        results = list(memory_map.resources())
        self.assertIs(results[0][0], ra)
        self.assertEqual(results[0][1], ("a",))
        self.assertEqual(results[0][2], (0, 1))

        self.assertIs(results[1][0], rd)
        self.assertEqual(results[1][1], ("b", "d"))
        self.assertEqual(results[1][2], (1, 2))

        self.assertIs(results[2][0], re)
        self.assertEqual(results[2][1], ("b", "e"))
        self.assertEqual(results[2][2], (2, 3))

        self.assertIs(results[3][0], rc)
        self.assertEqual(results[3][1], ("b", "c"))
        self.assertEqual(results[3][2], (3, 4))

        self.assertIs(results[4][0], rf)
        self.assertEqual(results[4][1], ("b", 0, "f"))
        self.assertEqual(results[4][2], (4, 5))

        self.assertIs(results[5][0], rg)
        self.assertEqual(results[5][1], ("b", 1, "g"))
        self.assertEqual(results[5][2], (6, 8))

    def test_memory_map_name_conflicts(self):
        # register/register
        regs_0 = Builder(addr_width=8, data_width=32)
        regs_0.add("a", _MockRegister("foo"))
        regs_0.add("a", _MockRegister("bar"))
        with self.assertRaisesRegex(ValueError,
                r"Resource _MockRegister\('bar'\) cannot be added to the local namespace:"
                r"\n- Name\('a'\) conflicts with local name Name\('a'\) assigned to "
                    r"_MockRegister\('foo'\)"):
            regs_0.as_memory_map()
        # register/cluster
        regs_1 = Builder(addr_width=8, data_width=32)
        regs_1.add("a", _MockRegister("foo"))
        with regs_1.Cluster("a"):
            regs_1.add("b", _MockRegister("bar"))
        with self.assertRaisesRegex(ValueError,
                r"Resource _MockRegister\('bar'\) cannot be added to the local namespace:"
                r"\n- Name\('a', 'b'\) conflicts with local name Name\('a'\) assigned to "
                    r"_MockRegister\('foo'\)"):
            regs_1.as_memory_map()
        # cluster/register
        regs_2 = Builder(addr_width=8, data_width=32)
        with regs_2.Cluster("a"):
            regs_2.add("b", _MockRegister("foo"))
        regs_2.add("a", _MockRegister("bar"))
        with self.assertRaisesRegex(ValueError,
                r"Resource _MockRegister\('bar'\) cannot be added to the local namespace:"
                r"\n- Name\('a'\) conflicts with local name Name\('a', 'b'\) assigned to "
                    r"_MockRegister\('foo'\)"):
            regs_2.as_memory_map()


class BridgeTestCase(unittest.TestCase):
    class _RWRegister(Register, access="rw"):
        def __init__(self, width, init=0):
            super().__init__({"a": Field(action.RW, width, init=init)})

    def test_wrong_memory_map(self):
        with self.assertRaisesRegex(TypeError,
                r"CSR bridge memory map must be an instance of MemoryMap, not 'foo'"):
            Bridge("foo")

    def test_wrong_memory_map_windows(self):
        memory_map_0 = MemoryMap(addr_width=1, data_width=8)
        memory_map_1 = MemoryMap(addr_width=1, data_width=8)
        memory_map_0.add_window(memory_map_1)
        with self.assertRaisesRegex(ValueError,
                r"CSR bridge memory map cannot have windows"):
            Bridge(memory_map_0)

    def test_wrong_memory_map_resource(self):
        class _Reg(wiring.Component):
            def __repr__(self):
                return "_Reg()"
        memory_map = MemoryMap(addr_width=1, data_width=8)
        memory_map.add_resource(_Reg({}), name=("a",), size=1)
        with self.assertRaisesRegex(TypeError,
                r"CSR register must be an instance of csr\.Register, not _Reg\(\)"):
            Bridge(memory_map)

    def test_sim(self):
        regs = Builder(addr_width=16, data_width=8)

        reg_rw_4 = regs.add("reg_rw_4", self._RWRegister(4, init=0x0))
        reg_rw_8 = regs.add("reg_rw_8", self._RWRegister(8, init=0x11))
        with regs.Cluster("cluster_0"):
            reg_rw_16 = regs.add("reg_rw_16", self._RWRegister(16, init=0x3322))

        dut = Bridge(regs.as_memory_map())

        async def testbench(ctx):
            ctx.set(dut.bus.addr, 0)
            ctx.set(dut.bus.r_stb, 1)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0xa)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0x0)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.r_stb), 1)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.w_stb), 1)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.w_stb), 0)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.w_stb), 0)
            ctx.set(dut.bus.r_stb, 0)
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(reg_rw_4.f.a.data), 0xa)

            ctx.set(dut.bus.addr, 1)
            ctx.set(dut.bus.r_stb, 1)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0xbb)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0x11)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.r_stb), 1)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.w_stb), 0)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.w_stb), 1)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.w_stb), 0)
            ctx.set(dut.bus.r_stb, 0)
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(reg_rw_8.f.a.data), 0xbb)

            ctx.set(dut.bus.addr, 2)
            ctx.set(dut.bus.r_stb, 1)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0xcc)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0x22)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.r_stb), 1)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.w_stb), 0)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.w_stb), 0)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.w_stb), 0)
            ctx.set(dut.bus.r_stb, 0)
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(reg_rw_16.f.a.data), 0x3322)

            ctx.set(dut.bus.addr, 3)
            ctx.set(dut.bus.r_stb, 1)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0xdd)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0x33)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.r_stb), 0)
            self.assertEqual(ctx.get(reg_rw_4 .f.a.port.w_stb), 0)
            self.assertEqual(ctx.get(reg_rw_8 .f.a.port.w_stb), 0)
            self.assertEqual(ctx.get(reg_rw_16.f.a.port.w_stb), 1)
            ctx.set(dut.bus.r_stb, 0)
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(reg_rw_16.f.a.data), 0xddcc)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

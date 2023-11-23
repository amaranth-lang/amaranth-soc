# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.sim import *

from amaranth_soc.csr.reg import *
from amaranth_soc.csr import field


class FieldPortSignatureTestCase(unittest.TestCase):
    def test_shape_1_ro(self):
        sig = FieldPort.Signature(1, "r")
        self.assertEqual(sig.shape, unsigned(1))
        self.assertEqual(sig.access, FieldPort.Access.R)
        self.assertEqual(sig.members, Signature({
            "r_data": In(unsigned(1)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(1)),
            "w_stb":  Out(1),
        }).members)

    def test_shape_8_rw(self):
        sig = FieldPort.Signature(8, "rw")
        self.assertEqual(sig.shape, unsigned(8))
        self.assertEqual(sig.access, FieldPort.Access.RW)
        self.assertEqual(sig.members, Signature({
            "r_data": In(unsigned(8)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(8)),
            "w_stb":  Out(1),
        }).members)

    def test_shape_10_wo(self):
        sig = FieldPort.Signature(10, "w")
        self.assertEqual(sig.shape, unsigned(10))
        self.assertEqual(sig.access, FieldPort.Access.W)
        self.assertEqual(sig.members, Signature({
            "r_data": In(unsigned(10)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(10)),
            "w_stb":  Out(1),
        }).members)

    def test_shape_0_rw(self):
        sig = FieldPort.Signature(0, "w")
        self.assertEqual(sig.shape, unsigned(0))
        self.assertEqual(sig.access, FieldPort.Access.W)
        self.assertEqual(sig.members, Signature({
            "r_data": In(unsigned(0)),
            "r_stb":  Out(1),
            "w_data": Out(unsigned(0)),
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
                r"Field shape must be a shape-castable object, not 'foo'"):
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

    def test_wrong_signature(self):
        with self.assertRaisesRegex(TypeError,
                r"This interface requires a csr\.FieldPort\.Signature, not 'foo'"):
            FieldPort("foo")


def _compatible_fields(a, b):
    return isinstance(a, Field) and type(a) == type(b) and \
           a.shape == b.shape and a.access == b.access


class FieldTestCase(unittest.TestCase):
    def test_simple(self):
        field = Field(unsigned(4), "rw")
        self.assertEqual(field.shape, unsigned(4))
        self.assertEqual(field.access, FieldPort.Access.RW)

    def test_compatible(self):
        self.assertTrue(_compatible_fields(Field(unsigned(4), "rw"),
                                           Field(unsigned(4), FieldPort.Access.RW)))
        self.assertFalse(_compatible_fields(Field(unsigned(3), "r" ), Field(unsigned(4), "r")))
        self.assertFalse(_compatible_fields(Field(unsigned(4), "rw"), Field(unsigned(4), "w")))
        self.assertFalse(_compatible_fields(Field(unsigned(4), "rw"), Field(unsigned(4), "r")))
        self.assertFalse(_compatible_fields(Field(unsigned(4), "r" ), Field(unsigned(4), "w")))

    def test_wrong_shape(self):
        with self.assertRaisesRegex(TypeError,
                r"Field shape must be a shape-castable object, not 'foo'"):
            Field("foo", "rw")

    def test_wrong_access(self):
        with self.assertRaisesRegex(ValueError, r"'wo' is not a valid FieldPort.Access"):
            Field(8, "wo")


class FieldMapTestCase(unittest.TestCase):
    def test_simple(self):
        field_map = FieldMap({
            "a": Field(unsigned(1), "r"),
            "b": Field(signed(3), "rw"),
            "c": FieldMap({
                "d": Field(unsigned(4), "rw"),
            }),
        })
        self.assertTrue(_compatible_fields(field_map["a"], Field(unsigned(1), "r")))
        self.assertTrue(_compatible_fields(field_map["b"], Field(signed(3), "rw")))
        self.assertTrue(_compatible_fields(field_map["c"]["d"], Field(unsigned(4), "rw")))

        self.assertTrue(_compatible_fields(field_map.a, Field(unsigned(1), "r")))
        self.assertTrue(_compatible_fields(field_map.b, Field(signed(3), "rw")))
        self.assertTrue(_compatible_fields(field_map.c.d, Field(unsigned(4), "rw")))

        self.assertEqual(len(field_map), 3)

    def test_iter(self):
        field_map = FieldMap({
            "a": Field(unsigned(1), "r"),
            "b": Field(signed(3), "rw")
        })
        self.assertEqual(list(field_map.items()), [
            ("a", field_map["a"]),
            ("b", field_map["b"]),
        ])

    def test_flatten(self):
        field_map = FieldMap({
            "a": Field(unsigned(1), "r"),
            "b": Field(signed(3), "rw"),
            "c": FieldMap({
                "d": Field(unsigned(4), "rw"),
            }),
        })
        self.assertEqual(list(field_map.flatten()), [
            (("a",), field_map["a"]),
            (("b",), field_map["b"]),
            (("c", "d"), field_map["c"]["d"]),
        ])

    def test_wrong_mapping(self):
        with self.assertRaisesRegex(TypeError,
                r"Fields must be provided as a non-empty mapping, not 'foo'"):
            FieldMap("foo")

    def test_wrong_field_key(self):
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not 1"):
            FieldMap({1: Field(unsigned(1), "rw")})
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not ''"):
            FieldMap({"": Field(unsigned(1), "rw")})

    def test_wrong_field_value(self):
        with self.assertRaisesRegex(TypeError,
                r"Field must be a Field or a FieldMap or a FieldArray, not unsigned\(1\)"):
            FieldMap({"a": unsigned(1)})

    def test_getitem_wrong_key(self):
        with self.assertRaises(KeyError):
            FieldMap({"a": Field(unsigned(1), "rw")})["b"]


class FieldArrayTestCase(unittest.TestCase):
    def test_simple(self):
        field_array = FieldArray([Field(unsigned(2), "rw") for _ in range(8)])
        self.assertEqual(len(field_array), 8)
        for i in range(8):
            self.assertTrue(_compatible_fields(field_array[i], Field(unsigned(2), "rw")))

    def test_dim_2(self):
        field_array = FieldArray([FieldArray([Field(unsigned(1), "rw") for _ in range(4)])
                                  for _ in range(4)])
        self.assertEqual(len(field_array), 4)
        for i in range(4):
            for j in range(4):
                self.assertTrue(_compatible_fields(field_array[i][j], Field(1, "rw")))

    def test_nested(self):
        field_array = FieldArray([
                FieldMap({
                    "a": Field(unsigned(4), "rw"),
                    "b": FieldArray([Field(unsigned(1), "rw") for _ in range(4)]),
                }) for _ in range(4)])
        self.assertEqual(len(field_array), 4)
        for i in range(4):
            self.assertTrue(_compatible_fields(field_array[i]["a"], Field(unsigned(4), "rw")))
            for j in range(4):
                self.assertTrue(_compatible_fields(field_array[i]["b"][j],
                                                   Field(unsigned(1), "rw")))

    def test_iter(self):
        field_array = FieldArray([Field(1, "rw") for _ in range(3)])
        self.assertEqual(list(field_array), [
            field_array[i] for i in range(3)
        ])

    def test_flatten(self):
        field_array = FieldArray([
                FieldMap({
                    "a": Field(4, "rw"),
                    "b": FieldArray([Field(1, "rw") for _ in range(2)]),
                }) for _ in range(2)])
        self.assertEqual(list(field_array.flatten()), [
            ((0, "a"), field_array[0]["a"]),
            ((0, "b", 0), field_array[0]["b"][0]),
            ((0, "b", 1), field_array[0]["b"][1]),
            ((1, "a"), field_array[1]["a"]),
            ((1, "b", 0), field_array[1]["b"][0]),
            ((1, "b", 1), field_array[1]["b"][1]),
        ])

    def test_wrong_field(self):
        with self.assertRaisesRegex(TypeError,
                r"Field must be a Field or a FieldMap or a FieldArray, not 'foo'"):
            FieldArray([Field(1, "rw"), "foo"])


class RegisterTestCase(unittest.TestCase):
    def test_simple(self):
        reg = Register("rw", FieldMap({
            "a": field.R(unsigned(1)),
            "b": field.RW1C(unsigned(3)),
            "c": FieldMap({"d": field.RW(signed(2))}),
            "e": FieldArray([field.W(unsigned(1)) for _ in range(2)])
        }))

        self.assertTrue(_compatible_fields(reg.f.a, field.R(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.b, field.RW1C(unsigned(3))))
        self.assertTrue(_compatible_fields(reg.f.c.d, field.RW(signed(2))))
        self.assertTrue(_compatible_fields(reg.f.e[0], field.W(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.e[1], field.W(unsigned(1))))

        self.assertEqual(reg.element.width, 8)
        self.assertEqual(reg.element.access.readable(), True)
        self.assertEqual(reg.element.access.writable(), True)

    def test_annotations(self):
        class MockRegister(Register):
            a: field.R(unsigned(1))
            b: field.RW1C(unsigned(3))
            c: FieldMap({"d": field.RW(signed(2))})
            e: FieldArray([field.W(unsigned(1)) for _ in range(2)])

            foo: unsigned(42)

        reg = MockRegister("rw")

        self.assertTrue(_compatible_fields(reg.f.a, field.R(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.b, field.RW1C(unsigned(3))))
        self.assertTrue(_compatible_fields(reg.f.c.d, field.RW(signed(2))))
        self.assertTrue(_compatible_fields(reg.f.e[0], field.W(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.e[1], field.W(unsigned(1))))

        self.assertEqual(reg.element.width, 8)
        self.assertEqual(reg.element.access.readable(), True)
        self.assertEqual(reg.element.access.writable(), True)

    def test_iter(self):
        reg = Register("rw", FieldMap({
            "a": field.R(unsigned(1)),
            "b": field.RW1C(unsigned(3)),
            "c": FieldMap({"d": field.RW(signed(2))}),
            "e": FieldArray([field.W(unsigned(1)) for _ in range(2)])
        }))
        self.assertEqual(list(reg), [
            (("a",), reg.f.a),
            (("b",), reg.f.b),
            (("c", "d"), reg.f.c.d),
            (("e", 0), reg.f.e[0]),
            (("e", 1), reg.f.e[1]),
        ])

    def test_sim(self):
        dut = Register("rw", FieldMap({
            "a": field.R(unsigned(1)),
            "b": field.RW1C(unsigned(3), reset=0b111),
            "c": FieldMap({"d": field.RW(signed(2), reset=-1)}),
            "e": FieldArray([field.W(unsigned(1)) for _ in range(2)]),
            "f": field.RW1S(unsigned(3)),
        }))

        def process():
            # Check reset values:

            self.assertEqual((yield dut.f.b  .data),  0b111)
            self.assertEqual((yield dut.f.c.d.data), -1)
            self.assertEqual((yield dut.f.f  .data),  0b000)

            self.assertEqual((yield dut.f.b   .port.r_data),  0b111)
            self.assertEqual((yield dut.f.c.d .port.r_data), -1)
            self.assertEqual((yield dut.f.f   .port.r_data),  0b000)

            # Initiator read:

            yield dut.element.r_stb.eq(1)
            yield Delay()

            self.assertEqual((yield dut.f.a.port.r_stb), 1)
            self.assertEqual((yield dut.f.b.port.r_stb), 1)
            self.assertEqual((yield dut.f.f.port.r_stb), 1)

            yield dut.element.r_stb.eq(0)

            # Initiator write:

            yield dut.element.w_stb .eq(1)
            yield dut.element.w_data.eq(Cat(
                Const(0b1,   1), # a
                Const(0b010, 3), # b
                Const(0b00,  2), # c.d
                Const(0b00,  2), # e
                Const(0b110, 3), # f
            ))
            yield Settle()

            self.assertEqual((yield dut.f.a   .port.w_stb), 0)
            self.assertEqual((yield dut.f.b   .port.w_stb), 1)
            self.assertEqual((yield dut.f.c.d .port.w_stb), 1)
            self.assertEqual((yield dut.f.e[0].port.w_stb), 1)
            self.assertEqual((yield dut.f.e[1].port.w_stb), 1)
            self.assertEqual((yield dut.f.f   .port.w_stb), 1)

            self.assertEqual((yield dut.f.b   .port.w_data), 0b010)
            self.assertEqual((yield dut.f.c.d .port.w_data), 0b00)
            self.assertEqual((yield dut.f.e[0].port.w_data), 0b0)
            self.assertEqual((yield dut.f.e[1].port.w_data), 0b0)
            self.assertEqual((yield dut.f.f   .port.w_data), 0b110)

            self.assertEqual((yield dut.f.e[0].w_data), 0b0)
            self.assertEqual((yield dut.f.e[1].w_data), 0b0)

            yield
            yield dut.element.w_stb.eq(0)
            yield Settle()

            self.assertEqual((yield dut.f.b  .data), 0b101)
            self.assertEqual((yield dut.f.c.d.data), 0b00)
            self.assertEqual((yield dut.f.f  .data), 0b110)

            # User write:

            yield dut.f.a.r_data.eq(0b1)
            yield dut.f.b.set   .eq(0b010)
            yield dut.f.f.clear .eq(0b010)
            yield Settle()

            self.assertEqual((yield dut.element.r_data),
                             Const.cast(Cat(
                                 Const(0b1,   1), # a
                                 Const(0b101, 3), # b
                                 Const(0b00,  2), # c.d
                                 Const(0b00,  2), # e
                                 Const(0b110, 3), # f
                             )).value)

            yield
            yield dut.f.a.r_data.eq(0b0)
            yield dut.f.b.set   .eq(0b000)
            yield dut.f.f.clear .eq(0b000)
            yield Settle()

            self.assertEqual((yield dut.element.r_data),
                             Const.cast(Cat(
                                 Const(0b0,   1), # a
                                 Const(0b111, 3), # b
                                 Const(0b00,  2), # c.d
                                 Const(0b00,  2), # e
                                 Const(0b100, 3), # f
                             )).value)

            # Concurrent writes:

            yield dut.element.w_stb .eq(1)
            yield dut.element.w_data.eq(Cat(
                Const(0b0,   1), # a
                Const(0b111, 3), # b
                Const(0b00,  2), # c.d
                Const(0b00,  2), # e
                Const(0b111, 3), # f
            ))

            yield dut.f.b.set  .eq(0b001)
            yield dut.f.f.clear.eq(0b111)
            yield
            yield Settle()

            self.assertEqual((yield dut.element.r_data),
                             Const.cast(Cat(
                                 Const(0b0,   1), # a
                                 Const(0b001, 3), # b
                                 Const(0b00,  2), # c.d
                                 Const(0b00,  2), # e
                                 Const(0b111, 3), # f
                             )).value)

            self.assertEqual((yield dut.f.b.data), 0b001)
            self.assertEqual((yield dut.f.f.data), 0b111)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class RegisterMapTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = RegisterMap()

    def test_add_register(self):
        reg_rw_a = Register("rw", FieldMap({"a": field.RW(1)}))
        self.assertIs(self.dut.add_register(reg_rw_a, name="reg_rw_a"), reg_rw_a)

    def test_add_register_frozen(self):
        self.dut.freeze()
        reg_rw_a = Register("rw", FieldMap({"a": field.RW(1)}))
        with self.assertRaisesRegex(ValueError, r"Register map is frozen"):
            self.dut.add_register(reg_rw_a, name="reg_rw_a")

    def test_add_register_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"Register must be an instance of csr\.Register, not 'foo'"):
            self.dut.add_register("foo", name="foo")

    def test_add_register_wrong_name(self):
        reg_rw_a = Register("rw", FieldMap({"a": field.RW(1)}))
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty string, not None"):
            self.dut.add_register(reg_rw_a, name=None)

    def test_add_register_empty_name(self):
        reg_rw_a = Register("rw", FieldMap({"a": field.RW(1)}))
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty string, not ''"):
            self.dut.add_register(reg_rw_a, name="")

    def test_add_cluster(self):
        cluster = RegisterMap()
        self.assertIs(self.dut.add_cluster(cluster, name="cluster"), cluster)

    def test_add_cluster_frozen(self):
        self.dut.freeze()
        cluster = RegisterMap()
        with self.assertRaisesRegex(ValueError, r"Register map is frozen"):
            self.dut.add_cluster(cluster, name="cluster")

    def test_add_cluster_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"Cluster must be an instance of csr\.RegisterMap, not 'foo'"):
            self.dut.add_cluster("foo", name="foo")

    def test_add_cluster_wrong_name(self):
        cluster = RegisterMap()
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty string, not None"):
            self.dut.add_cluster(cluster, name=None)

    def test_add_cluster_empty_name(self):
        cluster = RegisterMap()
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty string, not ''"):
            self.dut.add_cluster(cluster, name="")

    def test_namespace_collision(self):
        reg_rw_a  = Register("rw", FieldMap({"a": field.RW(1)}))
        reg_rw_b  = Register("rw", FieldMap({"b": field.RW(1)}))
        cluster_0 = RegisterMap()
        cluster_1 = RegisterMap()

        self.dut.add_register(reg_rw_a, name="reg_rw_a")
        self.dut.add_cluster(cluster_0, name="cluster_0")

        with self.assertRaisesRegex(ValueError, # register/register
                r"Name 'reg_rw_a' is already used by *"):
            self.dut.add_register(reg_rw_b, name="reg_rw_a")
        with self.assertRaisesRegex(ValueError, # register/cluster
                r"Name 'reg_rw_a' is already used by *"):
            self.dut.add_cluster(cluster_1, name="reg_rw_a")
        with self.assertRaisesRegex(ValueError, # cluster/cluster
                r"Name 'cluster_0' is already used by *"):
            self.dut.add_cluster(cluster_1, name="cluster_0")
        with self.assertRaisesRegex(ValueError, # cluster/register
                r"Name 'cluster_0' is already used by *"):
            self.dut.add_register(reg_rw_b, name="cluster_0")

    def test_iter_registers(self):
        reg_rw_a = Register("rw", FieldMap({"a": field.RW(1)}))
        reg_rw_b = Register("rw", FieldMap({"b": field.RW(1)}))
        self.dut.add_register(reg_rw_a, name="reg_rw_a")
        self.dut.add_register(reg_rw_b, name="reg_rw_b")

        registers = list(self.dut.registers())

        self.assertEqual(len(registers), 2)
        self.assertIs(registers[0][0], reg_rw_a)
        self.assertEqual(registers[0][1], "reg_rw_a")
        self.assertIs(registers[1][0], reg_rw_b)
        self.assertEqual(registers[1][1], "reg_rw_b")

    def test_iter_clusters(self):
        cluster_0 = RegisterMap()
        cluster_1 = RegisterMap()
        self.dut.add_cluster(cluster_0, name="cluster_0")
        self.dut.add_cluster(cluster_1, name="cluster_1")

        clusters = list(self.dut.clusters())

        self.assertEqual(len(clusters), 2)
        self.assertIs(clusters[0][0], cluster_0)
        self.assertEqual(clusters[0][1], "cluster_0")
        self.assertIs(clusters[1][0], cluster_1)
        self.assertEqual(clusters[1][1], "cluster_1")

    def test_iter_flatten(self):
        reg_rw_a  = Register("rw", FieldMap({"a": field.RW(1)}))
        reg_rw_b  = Register("rw", FieldMap({"b": field.RW(1)}))
        cluster_0 = RegisterMap()
        cluster_1 = RegisterMap()

        cluster_0.add_register(reg_rw_a, name="reg_rw_a")
        cluster_1.add_register(reg_rw_b, name="reg_rw_b")

        self.dut.add_cluster(cluster_0, name="cluster_0")
        self.dut.add_cluster(cluster_1, name="cluster_1")

        registers = list(self.dut.flatten())

        self.assertEqual(len(registers), 2)
        self.assertIs(registers[0][0], reg_rw_a)
        self.assertEqual(registers[0][1], ("cluster_0", "reg_rw_a"))
        self.assertIs(registers[1][0], reg_rw_b)
        self.assertEqual(registers[1][1], ("cluster_1", "reg_rw_b"))

    def test_get_path(self):
        reg_rw_a  = Register("rw", FieldMap({"a": field.RW(1)}))
        reg_rw_b  = Register("rw", FieldMap({"b": field.RW(1)}))
        cluster_0 = RegisterMap()

        cluster_0.add_register(reg_rw_a, name="reg_rw_a")
        self.dut.add_cluster(cluster_0, name="cluster_0")
        self.dut.add_register(reg_rw_b, name="reg_rw_b")

        self.assertEqual(self.dut.get_path(reg_rw_a), ("cluster_0", "reg_rw_a"))
        self.assertEqual(self.dut.get_path(reg_rw_b), ("reg_rw_b",))

    def test_get_path_wrong_register(self):
        with self.assertRaisesRegex(TypeError,
                r"Register must be an instance of csr\.Register, not 'foo'"):
            self.dut.get_path("foo")

    def test_get_path_unknown_register(self):
        reg_rw_a = Register("rw", FieldMap({"a": field.RW(1)}))
        with self.assertRaises(KeyError):
            self.dut.get_path(reg_rw_a)

    def test_get_register(self):
        reg_rw_a  = Register("rw", FieldMap({"a": field.RW(1)}))
        reg_rw_b  = Register("rw", FieldMap({"b": field.RW(1)}))
        cluster_0 = RegisterMap()

        cluster_0.add_register(reg_rw_a, name="reg_rw_a")
        self.dut.add_cluster(cluster_0, name="cluster_0")
        self.dut.add_register(reg_rw_b, name="reg_rw_b")

        self.assertIs(self.dut.get_register(("cluster_0", "reg_rw_a")), reg_rw_a)
        self.assertIs(self.dut.get_register(("reg_rw_b",)), reg_rw_b)

    def test_get_register_empty_path(self):
        with self.assertRaisesRegex(ValueError, r"Path must be a non-empty iterable"):
            self.dut.get_register(())

    def test_get_register_wrong_path(self):
        with self.assertRaisesRegex(TypeError,
                r"Path must contain non-empty strings, not 0"):
            self.dut.get_register(("cluster_0", 0))
        with self.assertRaisesRegex(TypeError,
                r"Path must contain non-empty strings, not ''"):
            self.dut.get_register(("", "reg_rw_a"))

    def test_get_register_unknown_path(self):
        with self.assertRaises(KeyError):
            self.dut.get_register(("reg_rw_a",))


class BridgeTestCase(unittest.TestCase):
    def test_memory_map(self):
        reg_rw_4  = Register("rw", FieldMap({"a": field.RW( 4)}))
        reg_rw_8  = Register("rw", FieldMap({"a": field.RW( 8)}))
        reg_rw_12 = Register("rw", FieldMap({"a": field.RW(12)}))
        reg_rw_16 = Register("rw", FieldMap({"a": field.RW(16)}))

        cluster_0 = RegisterMap()
        cluster_0.add_register(reg_rw_12, name="reg_rw_12")
        cluster_0.add_register(reg_rw_16, name="reg_rw_16")

        register_map = RegisterMap()
        register_map.add_register(reg_rw_4, name="reg_rw_4")
        register_map.add_register(reg_rw_8, name="reg_rw_8")
        register_map.add_cluster(cluster_0, name="cluster_0")

        dut = Bridge(register_map, addr_width=16, data_width=8)
        registers = list(dut.bus.memory_map.resources())

        self.assertIs(registers[0][0], reg_rw_4.element)
        self.assertEqual(registers[0][1], "reg_rw_4")
        self.assertEqual(registers[0][2], (0, 1))

        self.assertIs(registers[1][0], reg_rw_8.element)
        self.assertEqual(registers[1][1], "reg_rw_8")
        self.assertEqual(registers[1][2], (1, 2))

        self.assertIs(registers[2][0], reg_rw_12.element)
        self.assertEqual(registers[2][1], "cluster_0__reg_rw_12")
        self.assertEqual(registers[2][2], (2, 4))

        self.assertIs(registers[3][0], reg_rw_16.element)
        self.assertEqual(registers[3][1], "cluster_0__reg_rw_16")
        self.assertEqual(registers[3][2], (4, 6))

        Fragment.get(dut, platform=None) # silence UnusedElaboratable

    def test_wrong_register_map(self):
        with self.assertRaisesRegex(TypeError,
                r"Register map must be an instance of RegisterMap, not 'foo'"):
            dut = Bridge("foo", addr_width=16, data_width=8)

    def test_register_addr(self):
        reg_rw_4  = Register("rw", FieldMap({"a": field.RW( 4)}))
        reg_rw_8  = Register("rw", FieldMap({"a": field.RW( 8)}))
        reg_rw_12 = Register("rw", FieldMap({"a": field.RW(12)}))
        reg_rw_16 = Register("rw", FieldMap({"a": field.RW(16)}))

        cluster_0 = RegisterMap()
        cluster_0.add_register(reg_rw_12, name="reg_rw_12")
        cluster_0.add_register(reg_rw_16, name="reg_rw_16")

        register_map = RegisterMap()
        register_map.add_register(reg_rw_4, name="reg_rw_4")
        register_map.add_register(reg_rw_8, name="reg_rw_8")
        register_map.add_cluster(cluster_0, name="cluster_0")

        register_addr = {
            "reg_rw_4": 0x10,
            "reg_rw_8": None,
            "cluster_0": {
                "reg_rw_12": 0x20,
                "reg_rw_16": None,
            },
        }

        dut = Bridge(register_map, addr_width=16, data_width=8,
                     register_addr=register_addr)
        registers = list(dut.bus.memory_map.resources())

        self.assertEqual(registers[0][1], "reg_rw_4")
        self.assertEqual(registers[0][2], (0x10, 0x11))

        self.assertEqual(registers[1][1], "reg_rw_8")
        self.assertEqual(registers[1][2], (0x11, 0x12))

        self.assertEqual(registers[2][1], "cluster_0__reg_rw_12")
        self.assertEqual(registers[2][2], (0x20, 0x22))

        self.assertEqual(registers[3][1], "cluster_0__reg_rw_16")
        self.assertEqual(registers[3][2], (0x22, 0x24))

        Fragment.get(dut, platform=None) # silence UnusedElaboratable

    def test_register_alignment(self):
        reg_rw_4  = Register("rw", FieldMap({"a": field.RW( 4)}))
        reg_rw_8  = Register("rw", FieldMap({"a": field.RW( 8)}))
        reg_rw_12 = Register("rw", FieldMap({"a": field.RW(12)}))
        reg_rw_16 = Register("rw", FieldMap({"a": field.RW(16)}))

        cluster_0 = RegisterMap()
        cluster_0.add_register(reg_rw_12, name="reg_rw_12")
        cluster_0.add_register(reg_rw_16, name="reg_rw_16")

        register_map = RegisterMap()
        register_map.add_register(reg_rw_4, name="reg_rw_4")
        register_map.add_register(reg_rw_8, name="reg_rw_8")
        register_map.add_cluster(cluster_0, name="cluster_0")

        register_alignment = {
            "reg_rw_4": None,
            "reg_rw_8": None,
            "cluster_0": {
                "reg_rw_12": 3,
                "reg_rw_16": None,
            },
        }

        dut = Bridge(register_map, addr_width=16, data_width=8, alignment=1,
                     register_alignment=register_alignment)
        registers = list(dut.bus.memory_map.resources())

        self.assertEqual(registers[0][1], "reg_rw_4")
        self.assertEqual(registers[0][2], (0, 2))

        self.assertEqual(registers[1][1], "reg_rw_8")
        self.assertEqual(registers[1][2], (2, 4)),

        self.assertEqual(registers[2][1], "cluster_0__reg_rw_12")
        self.assertEqual(registers[2][2], (8, 16))

        self.assertEqual(registers[3][1], "cluster_0__reg_rw_16")
        self.assertEqual(registers[3][2], (16, 18))

        Fragment.get(dut, platform=None) # silence UnusedElaboratable

    def test_register_out_of_bounds(self):
        reg_rw_24 = Register("rw", FieldMap({"a": field.RW(24)}))
        register_map = RegisterMap()
        register_map.add_register(reg_rw_24, name="reg_rw_24")
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x0\.\.0x3 out of bounds for memory map spanning "
                r"range 0x0\.\.0x2 \(1 address bits\)"):
            dut = Bridge(register_map, addr_width=1, data_width=8)

    def test_wrong_register_address(self):
        reg_rw_4 = Register("rw", FieldMap({"a": field.RW(4)}))
        register_map = RegisterMap()
        register_map.add_register(reg_rw_4, name="reg_rw_4")
        with self.assertRaisesRegex(TypeError, r"Register address must be a mapping, not 'foo'"):
            dut = Bridge(register_map, addr_width=1, data_width=8, register_addr="foo")

    def test_wrong_cluster_address(self):
        reg_rw_4  = Register("rw", FieldMap({"a": field.RW(4)}))
        cluster_0 = RegisterMap()
        cluster_0.add_register(reg_rw_4, name="reg_rw_4")
        register_map = RegisterMap()
        register_map.add_cluster(cluster_0, name="cluster_0")
        with self.assertRaisesRegex(TypeError,
                r"Register address \('cluster_0',\) must be a mapping, not 'foo'"):
            dut = Bridge(register_map, addr_width=1, data_width=8,
                         register_addr={"cluster_0": "foo"})

    def test_wrong_register_alignment(self):
        reg_rw_4 = Register("rw", FieldMap({"a": field.RW(4)}))
        register_map = RegisterMap()
        register_map.add_register(reg_rw_4, name="reg_rw_4")
        with self.assertRaisesRegex(TypeError, r"Register alignment must be a mapping, not 'foo'"):
            dut = Bridge(register_map, addr_width=1, data_width=8, register_alignment="foo")

    def test_wrong_cluster_alignment(self):
        reg_rw_4  = Register("rw", FieldMap({"a": field.RW(4)}))
        cluster_0 = RegisterMap()
        cluster_0.add_register(reg_rw_4, name="reg_rw_4")
        register_map = RegisterMap()
        register_map.add_cluster(cluster_0, name="cluster_0")
        with self.assertRaisesRegex(TypeError,
                r"Register alignment \('cluster_0',\) must be a mapping, not 'foo'"):
            dut = Bridge(register_map, addr_width=1, data_width=8,
                         register_alignment={"cluster_0": "foo"})

    def test_sim(self):
        reg_rw_4  = Register("rw", FieldMap({"a": field.RW( 4, reset=0x0)}))
        reg_rw_8  = Register("rw", FieldMap({"a": field.RW( 8, reset=0x11)}))
        reg_rw_16 = Register("rw", FieldMap({"a": field.RW(16, reset=0x3322)}))

        cluster_0 = RegisterMap()
        cluster_0.add_register(reg_rw_16, name="reg_rw_16")

        register_map = RegisterMap()
        register_map.add_register(reg_rw_4, name="reg_rw_4")
        register_map.add_register(reg_rw_8, name="reg_rw_8")
        register_map.add_cluster(cluster_0, name="cluster_0")

        dut = Bridge(register_map, addr_width=16, data_width=8)

        def process():
            yield dut.bus.addr.eq(0)
            yield dut.bus.r_stb.eq(1)
            yield dut.bus.w_stb.eq(1)
            yield dut.bus.w_data.eq(0xa)
            yield
            yield Settle()
            self.assertEqual((yield dut.bus.r_data), 0x0)
            self.assertEqual((yield reg_rw_4 .f.a.port.r_stb), 1)
            self.assertEqual((yield reg_rw_8 .f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_16.f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_4 .f.a.port.w_stb), 1)
            self.assertEqual((yield reg_rw_8 .f.a.port.w_stb), 0)
            self.assertEqual((yield reg_rw_16.f.a.port.w_stb), 0)
            yield dut.bus.r_stb.eq(0)
            yield dut.bus.w_stb.eq(0)
            yield
            yield Settle()
            self.assertEqual((yield reg_rw_4.f.a.data), 0xa)

            yield dut.bus.addr.eq(1)
            yield dut.bus.r_stb.eq(1)
            yield dut.bus.w_stb.eq(1)
            yield dut.bus.w_data.eq(0xbb)
            yield
            yield Settle()
            self.assertEqual((yield dut.bus.r_data), 0x11)
            self.assertEqual((yield reg_rw_4 .f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_8 .f.a.port.r_stb), 1)
            self.assertEqual((yield reg_rw_16.f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_4 .f.a.port.w_stb), 0)
            self.assertEqual((yield reg_rw_8 .f.a.port.w_stb), 1)
            self.assertEqual((yield reg_rw_16.f.a.port.w_stb), 0)
            yield dut.bus.r_stb.eq(0)
            yield dut.bus.w_stb.eq(0)
            yield
            yield Settle()
            self.assertEqual((yield reg_rw_8.f.a.data), 0xbb)

            yield dut.bus.addr.eq(2)
            yield dut.bus.r_stb.eq(1)
            yield dut.bus.w_stb.eq(1)
            yield dut.bus.w_data.eq(0xcc)
            yield
            yield Settle()
            self.assertEqual((yield dut.bus.r_data), 0x22)
            self.assertEqual((yield reg_rw_4 .f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_8 .f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_16.f.a.port.r_stb), 1)
            self.assertEqual((yield reg_rw_4 .f.a.port.w_stb), 0)
            self.assertEqual((yield reg_rw_8 .f.a.port.w_stb), 0)
            self.assertEqual((yield reg_rw_16.f.a.port.w_stb), 0)
            yield dut.bus.r_stb.eq(0)
            yield dut.bus.w_stb.eq(0)
            yield
            yield Settle()
            self.assertEqual((yield reg_rw_16.f.a.data), 0x3322)

            yield dut.bus.addr.eq(3)
            yield dut.bus.r_stb.eq(1)
            yield dut.bus.w_stb.eq(1)
            yield dut.bus.w_data.eq(0xdd)
            yield
            yield Settle()
            self.assertEqual((yield dut.bus.r_data), 0x33)
            self.assertEqual((yield reg_rw_4 .f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_8 .f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_16.f.a.port.r_stb), 0)
            self.assertEqual((yield reg_rw_4 .f.a.port.w_stb), 0)
            self.assertEqual((yield reg_rw_8 .f.a.port.w_stb), 0)
            self.assertEqual((yield reg_rw_16.f.a.port.w_stb), 1)
            yield dut.bus.r_stb.eq(0)
            yield dut.bus.w_stb.eq(0)
            yield
            yield Settle()
            self.assertEqual((yield reg_rw_16.f.a.data), 0xddcc)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

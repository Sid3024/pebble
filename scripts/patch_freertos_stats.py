from pathlib import Path

Import("env")


def patch_file(target, old, new, label):
    if not target.exists():
        print(f"{label}: missing file: {target}")
        return

    content = target.read_text(encoding="utf-8")
    if old not in content:
        if new in content:
            print(f"{label}: already applied")
        else:
            print(f"{label}: target text not found")
        return

    target.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_framework_sources():
    framework_dir = env.PioPlatform().get_package_dir("framework-arduinoespressif32")
    if not framework_dir:
        print("framework patch: framework-arduinoespressif32 not found")
        return

    patch_file(
        Path(framework_dir) / "cores" / "esp32" / "esp32-hal-i2c-slave.c",
        "  i2c_ll_slave_init(i2c->dev);",
        "  typeof(i2c->dev->ctr) ctrl_reg;\n  ctrl_reg.val = 0;\n  ctrl_reg.sda_force_out = 1;\n  ctrl_reg.scl_force_out = 1;\n  i2c->dev->ctr.val = ctrl_reg.val;\n  i2c->dev->fifo_conf.fifo_addr_cfg_en = 0;",
        "esp32-hal-i2c-slave patch",
    )


patch_framework_sources()
#!/usr/bin/env python3

import sys
import asyncio
import logging
import traceback
from contextlib import suppress

# fix tee buffering
sys.stdout.reconfigure(line_buffering=True)

from bbot.core import CORE

from bbot import __version__
from bbot.core.errors import *
from bbot.core.helpers.logger import log_to_stderr

log = logging.getLogger("bbot.cli")

err = False
scan_name = ""


async def _main():
    from bbot.scanner import Scanner
    from bbot.scanner.preset import Preset

    global scan_name

    try:

        # start by creating a default scan preset
        preset = Preset(_log=True, name="bbot_cli_main")
        # populate preset symlinks
        preset.all_presets
        # parse command line arguments and merge into preset
        try:
            preset.parse_args()
        except BBOTArgumentError as e:
            log_to_stderr(str(e), level="WARNING")
            log.trace(traceback.format_exc())
            return
        # ensure arguments (-c config options etc.) are valid
        options = preset.args.parsed

        # print help if no arguments
        if len(sys.argv) == 1:
            log.stdout(preset.args.parser.format_help())
            sys.exit(1)
            return

        # --version
        if options.version:
            log.stdout(__version__)
            sys.exit(0)
            return

        # --list-presets
        if options.list_presets:
            log.stdout("")
            log.stdout("### PRESETS ###")
            log.stdout("")
            for row in preset.presets_table().splitlines():
                log.stdout(row)
            return

        # if we're listing modules or their options
        if options.list_modules or options.list_module_options:

            # if no modules or flags are specified, enable everything
            if not (options.modules or options.output_modules or options.flags):
                for module, preloaded in preset.module_loader.preloaded().items():
                    module_type = preloaded.get("type", "scan")
                    preset.add_module(module, module_type=module_type)

            preset.bake()

            # --list-modules
            if options.list_modules:
                log.stdout("")
                log.stdout("### MODULES ###")
                log.stdout("")
                for row in preset.module_loader.modules_table(preset.modules).splitlines():
                    log.stdout(row)
                return

            # --list-module-options
            if options.list_module_options:
                log.stdout("")
                log.stdout("### MODULE OPTIONS ###")
                log.stdout("")
                for row in preset.module_loader.modules_options_table(preset.modules).splitlines():
                    log.stdout(row)
                return

        # --list-flags
        if options.list_flags:
            flags = preset.flags if preset.flags else None
            log.stdout("")
            log.stdout("### FLAGS ###")
            log.stdout("")
            for row in preset.module_loader.flags_table(flags=flags).splitlines():
                log.stdout(row)
            return

        try:
            scan = Scanner(preset=preset)
        except (PresetAbortError, ValidationError) as e:
            log.warning(str(e))
            return

        deadly_modules = [
            m for m in scan.preset.scan_modules if "deadly" in preset.preloaded_module(m).get("flags", [])
        ]
        if deadly_modules and not options.allow_deadly:
            log.hugewarning(f"You enabled the following deadly modules: {','.join(deadly_modules)}")
            log.hugewarning(f"Deadly modules are highly intrusive")
            log.hugewarning(f"Please specify --allow-deadly to continue")
            return False

        # --current-preset
        if options.current_preset:
            print(scan.preset.to_yaml())
            sys.exit(0)
            return

        # --current-preset-full
        if options.current_preset_full:
            print(scan.preset.to_yaml(full_config=True))
            sys.exit(0)
            return

        # --install-all-deps
        if options.install_all_deps:
            all_modules = list(preset.module_loader.preloaded())
            scan.helpers.depsinstaller.force_deps = True
            succeeded, failed = await scan.helpers.depsinstaller.install(*all_modules)
            log.info("Finished installing module dependencies")
            return False if failed else True

        scan_name = str(scan.name)
        scan.helpers.word_cloud.load()
        await scan._prep()

        if not options.dry_run:
            log.trace(f"Command: {' '.join(sys.argv)}")

            if sys.stdin.isatty():
                if not options.yes:
                    log.hugesuccess(f"Scan ready. Press enter to execute {scan.name}")
                    input()

        await scan.async_start_without_generator()

        return True

    finally:
        # save word cloud
        with suppress(BaseException):
            save_success, filename = scan.helpers.word_cloud.save()
            if save_success:
                log_to_stderr(f"Saved word cloud ({len(scan.helpers.word_cloud):,} words) to {filename}")
        # remove output directory if empty
        with suppress(BaseException):
            scan.home.rmdir()


def main():
    global scan_name
    try:
        asyncio.run(_main())
    except asyncio.CancelledError:
        if CORE.logger.log_level <= logging.DEBUG:
            log_to_stderr(traceback.format_exc(), level="DEBUG")
    except KeyboardInterrupt:
        msg = "Interrupted"
        if scan_name:
            msg = f"You killed {scan_name}"
        log_to_stderr(msg, level="WARNING")
        if CORE.logger.log_level <= logging.DEBUG:
            log_to_stderr(traceback.format_exc(), level="DEBUG")
        exit(1)


if __name__ == "__main__":
    main()

from bbot.modules.base import BaseModule


"""
wrapper for https://github.com/defparam/smuggler.git
"""


class smuggler(BaseModule):

    watched_events = ["URL"]
    produced_events = ["FINDING"]
    flags = ["active", "aggressive"]

    in_scope_only = True

    deps_ansible = [
        {
            "name": "Get smuggler repo",
            "git": {
                "repo": "https://github.com/defparam/smuggler.git",
                "dest": "{BBOT_TOOLS}/smuggler",
            },
        }
    ]

    def handle_event(self, event):

        command = [
            "python",
            f"{self.scan.helpers.tools_dir}/smuggler/smuggler.py",
            "--no-color",
            "-q",
            "-u",
            event.data,
        ]
        for f in self.helpers.run_live(command):
            if "Issue Found" in f:
                technique = f.split(":")[0].rstrip()
                text = f.split(":")[1].split("-")[0].strip()
                self.emit_event(f"[HTTP SMUGGLER] [{text}] Technique: {technique}", "FINDING", source=event)

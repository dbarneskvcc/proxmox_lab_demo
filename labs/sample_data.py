"""
Hard-coded lab content so the sample has something to show.
A real version would move this into models (Lab, Task, Question) and the admin.

`vmid` is the Proxmox VM id the lab runs on. The student's Proxmox account must
have permission on that VM, or the workspace shows "VM not available".
"""

LABS = [
    {
        "id": "linux-basics",
        "title": "Linux Basics",
        "icon": "bi-terminal",
        "description": "Get comfortable navigating the filesystem and managing files from the shell.",
        "vmid": 100,
        "tasks": [
            {
                "title": "Log in and find your bearings",
                "instructions": "<p>Log in to the VM with the credentials provided. Then print your "
                                "current directory and list its contents.</p>"
                                '<pre class="cmd">pwd\nls -la</pre>',
                "questions": [
                    {"type": "text", "label": "What is the full path of your home directory?"},
                    {"type": "radio", "label": "Which flag shows hidden files?",
                     "options": ["-h", "-a", "-l", "-r"]},
                ],
            },
            {
                "title": "Create a directory structure",
                "instructions": "<p>Create a <code>projects</code> folder with two subfolders, "
                                "<code>web</code> and <code>scripts</code>.</p>"
                                '<pre class="cmd">mkdir -p ~/projects/{web,scripts}</pre>',
                "questions": [
                    {"type": "textarea", "label": "Paste the output of <code>tree ~/projects</code>."},
                ],
            },
            {
                "title": "File permissions",
                "instructions": "<p>Create a script file and make it executable.</p>"
                                '<pre class="cmd">touch ~/projects/scripts/hello.sh\n'
                                "chmod +x ~/projects/scripts/hello.sh</pre>",
                "questions": [
                    {"type": "text", "label": "What permission string does <code>ls -l</code> show for hello.sh?"},
                ],
            },
        ],
    },
    {
        "id": "networking",
        "title": "Networking Fundamentals",
        "icon": "bi-diagram-3",
        "description": "Inspect network interfaces, test connectivity, and look up DNS records.",
        "vmid": 101,
        "tasks": [
            {
                "title": "Inspect interfaces",
                "instructions": '<p>List the network interfaces on the VM.</p><pre class="cmd">ip addr show</pre>',
                "questions": [{"type": "text", "label": "What is the IPv4 address of the primary interface?"}],
            },
            {
                "title": "Test connectivity",
                "instructions": '<p>Ping an external host.</p><pre class="cmd">ping -c 4 8.8.8.8</pre>',
                "questions": [{"type": "text", "label": "What was the average round-trip time?"}],
            },
        ],
    },
]

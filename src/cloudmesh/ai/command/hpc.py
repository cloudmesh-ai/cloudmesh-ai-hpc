import click
import webbrowser
import csv
import os
import re
import asyncio
import questionary
from typing import Optional, Any
from cloudmesh.ai.common.io import console
from cloudmesh.ai.vpn.vpn import Vpn
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Static
from textual import work
from cloudmesh.ai.hpc import Hpc


@click.group()
def hpc_group():
    """
    HPC tool for Cloudmesh AI.
    This command simplifies access to HPC resources.
    """
    pass


# --- Storage Group ---
@hpc_group.group(name="storage")
def storage_group():
    """Storage related commands."""
    pass


@storage_group.command(name="info")
@click.argument("directory")
@click.option("--info", is_flag=True, help="Detailed information")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def storage_info(directory: str, info: bool, debug: bool) -> None:
    """Obtains information about the storage associated with a directory on HPC."""
    hpc = Hpc(debug=debug)

    console.print("\n[bold]HPC Configuration Info[/bold]")
    console.print(f"Current Host      : {hpc.host}")
    console.print("")

    result = hpc.storage(directory)
    console.table(["Directory", "Size"], [[directory, result]], title="Storage Info")


# --- VPN Group ---
@hpc_group.group(name="vpn")
def vpn_group():
    """VPN related commands."""
    pass


@vpn_group.command(name="on")
def vpn_on() -> None:
    """Switches the VPN on."""
    vpn = Vpn(service="hpc")
    vpn.connect()


@vpn_group.command(name="off")
def vpn_off() -> None:
    """Switches the VPN off."""
    vpn = Vpn(service="hpc")
    vpn.disconnect()


@vpn_group.command(name="info")
def vpn_info() -> None:
    """Prints information about the current connection to the internet."""
    vpn = Vpn(service="hpc")
    vpn.info()


@vpn_group.command(name="status")
def vpn_status() -> None:
    """Prints True if VPN is enabled, False if not."""
    vpn = Vpn(service="hpc")
    enabled = vpn.enabled()
    console.print(f"VPN Enabled: {enabled}")


# --- Slurm Group ---
@hpc_group.group(name="slurm")
def slurm_group():
    """Slurm related commands."""
    pass


@slurm_group.command(name="info")
@click.argument("key", required=False)
def slurm_info(key: Optional[str]) -> None:
    """Prints Slurm directive information for a partition key."""
    hpc = Hpc()
    if not key:
        console.error("Please provide a partition key.")
        return
    directives = hpc.create_slurm_directives(hpc.host, key)
    console.print(directives)


@slurm_group.command(name="job-info")
@click.argument("job_id")
def slurm_job_info(job_id: str) -> None:
    """Get detailed information about a Slurm job."""
    hpc = Hpc()
    result = hpc.job_info(job_id)
    console.print(result)


@slurm_group.command(name="submit")
@click.argument("script")
@click.option("--key", help="Partition key")
@click.option("--sbatch", help="Additional sbatch parameters (key:val,key:val)")
def slurm_submit(script: str, key: Optional[str], sbatch: Optional[str]) -> None:
    """Upload a script and submit it as a Slurm job."""
    hpc = Hpc()
    try:
        sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
        result = hpc.submit(script, key=key, sbatch_params=sbatch_params)
        console.print(result)
    except Exception as e:
        console.error(e)


@slurm_group.command(name="logs")
@click.argument("job_id")
@click.option("--tail", is_flag=True, help="Show the last few lines of the log files")
@click.option("--follow", is_flag=True, help="Stream the log files in real-time")
def slurm_logs(job_id: str, tail: bool, follow: bool) -> None:
    """Read the Slurm output logs for a job."""
    hpc = Hpc()
    result = hpc.logs(job_id, tail=tail, follow=follow)
    if result:
        console.print(result)


@slurm_group.command(name="quota")
@click.option("--billing", is_flag=True, help="Show core-hour and billing usage")
def slurm_quota(billing: bool) -> None:
    """Check disk quota or billing usage on the HPC."""
    hpc = Hpc()
    if billing:
        result = hpc.get_billing_usage()
        if not result:
            console.error("No billing usage data found.")
            return
        
        header = list(result[0].keys())
        data = [[row.get(k, "N/A") for k in header] for row in result]
        console.table(header, data, title="Slurm Billing/Usage Report")
    else:
        result = hpc.quota()
        console.print(result)


@hpc_group.command(name="sreport")
@click.argument("username", required=False)
@click.option("--start", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (YYYY-MM-DD)")
@click.option("--stat", is_flag=True, help="Enable statistics mode")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_sreport(
    username: Optional[str],
    start: Optional[str],
    end: Optional[str],
    stat: bool,
    debug: bool,
) -> None:
    """Get Slurm usage reports for users, accounts, partitions, and nodes."""
    hpc = Hpc(debug=debug)

    entities = ["user", "account", "partition", "node"]

    for entity in entities:
        # Use username as filter for 'user' and 'account' entities
        filter_val = username if entity in ["user", "account"] else None

        result = hpc.sreport(
            entity=entity, filter_val=filter_val, start=start, end=end, stat=stat
        )

        if not result:
            console.print(f"No {entity} usage report found.")
            continue

        # Use the keys of the first dictionary as the table header
        header = list(result[0].keys())
        data = [[row.get(k, "N/A") for k in header] for row in result]

        title = f"Slurm {entity.capitalize()} Usage Report"
        if filter_val:
            title += f" ({filter_val})"

        console.table(header, data, title=title)


@hpc_group.command(name="squeue")
@click.argument("host", required=False)
@click.option("--search", help="Filter jobs by node name using regex")
@click.option(
    "--output",
    default="table",
    type=click.Choice(["table", "attributes"]),
    help="Output format",
)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_squeue(
    host: Optional[str], search: Optional[str], output: str, debug: bool
) -> None:
    """Get Slurm queue information."""
    hpc = Hpc(host=host, debug=debug) if host else Hpc(debug=debug)

    if search:
        result = hpc.search_jobs_by_node(search)
        if not result:
            console.print(f"No jobs found running on nodes matching: {search}")
            return

        if output == "attributes":
            for i, job in enumerate(result, 1):
                console.print(f"\n[bold]Job {i}: {job['JobID']}[/bold]")
                for key, value in job.items():
                    console.print(f"  {key.ljust(15)} : {value}")
        else:
            header = list(result[0].keys())
            data = [[row.get(k, "N/A") for k in header] for row in result]
            console.table(header, data, title=f"Jobs on nodes matching: {search}")
    else:
        result = hpc.list_jobs()
        if not result:
            console.print("No active jobs found.")
            return
        console.print(result)


@hpc_group.command(name="sinfo")
@click.argument("host", required=False)
@click.option(
    "--query",
    default="all",
    help="Sinfo query format (all, summarize, long, Node, long_node, list_reasons, long_list_reasons)",
)
@click.option(
    "--output",
    default="attributes",
    type=click.Choice(["json", "yaml", "attributes", "table", "summary"]),
    help="Output format",
)
@click.option(
    "--format", help="Shortcut for output format (json, yaml, table) or query format"
)
@click.option("--partition", help="Partition to check")
@click.option("--search", help="Filter nodes by attribute value using regex")
def slurm_sinfo(
    host: Optional[str],
    query: str,
    output: str,
    format: Optional[str],
    partition: Optional[str],
    search: Optional[str],
) -> None:
    """Get Slurm node information."""
    # Resolve host: if not provided, Hpc() uses default (e.g., "uva")
    hpc = Hpc(host=host) if host else Hpc()

    # Handle --format shortcut
    if format:
        if format in ["json", "yaml", "table", "attributes"]:
            output = format
        else:
            query = format

    # Map "all" to "%all" for the library method
    fmt = "%all" if query == "all" else query

    result = hpc.sinfo(partition=partition, format=fmt)

    if not result:
        console.print("No information found.")
        return

    # Extract summary from the first node (since it's merged into all nodes)
    summary = result[0] if result else {}
    if "nodes_available" in summary:
        console.print("\n[bold]Partition Summary[/bold]")
        console.print(f"  NODES_AVAILABLE : {summary.get('nodes_available')}")
        console.print(f"  NODES_IDLE      : {summary.get('nodes_idle')}")
        console.print(f"  CPUS_AVAILABLE  : {summary.get('cpus_available')}")
        console.print(f"  CPUS_IDLE       : {summary.get('cpus_idle')}")
        console.print(f"  CPUS_O          : {summary.get('cpus_other')}")
        console.print(f"  CPUS_T          : {summary.get('cpus_total')}")
        console.print()

    if search:
        # Filter results: keep node if any attribute value matches the regex
        filtered_result = []
        try:
            regex = re.compile(search, re.IGNORECASE)
            for node in result:
                if any(regex.search(str(val)) for val in node.values()):
                    filtered_result.append(node)
            result = filtered_result
        except re.error as e:
            console.error(f"Invalid search regex: {e}")
            return

    if not result:
        console.print("No nodes matched the search criteria.")
        return

    if output == "json":
        console.print_json(result)
    elif output == "yaml":
        console.print_yaml(result)
    elif output == "summary":
        total_nodes = len(result)
        states = {}
        total_cpus = 0
        idle_cpus = 0
        total_gpus = 0
        idle_gpus = 0
        feature_gpus = {}

        # To accurately count idle GPUs on 'mixed' nodes, we need scontrol data
        node_gpu_usage = {}
        mix_nodes = [
            n.get("HOSTNAMES") or n.get("node")
            for n in result
            if "mix" in (n.get("STATE") or n.get("state", "")).lower()
        ]

        if mix_nodes:
            nodes_list = ",".join(mix_nodes)
            sctrl_output = hpc.run_command(f"scontrol show node {nodes_list}")
            if sctrl_output:
                node_blocks = sctrl_output.split("NodeName=")[1:]
                for block in node_blocks:
                    # NodeName is usually the first word after "NodeName="
                    node_name = block.split()[0]
                    # More robust regex to handle both = and : and potential (S:...) suffixes
                    alloc_match = re.search(
                        r"AllocTRES=[^=]*gres/gpu[:=]([^,\s\)]+)", block
                    )
                    if alloc_match:
                        val = alloc_match.group(1)
                        # Extract the number from the end of the value (e.g., "1" from "1" or "1" from "1(S:0)")
                        num_match = re.search(r"(\d+)", val)
                        node_gpu_usage[node_name] = (
                            int(num_match.group(1)) if num_match else 0
                        )
                    else:
                        # If AllocTRES is missing or doesn't mention GPUs, assume 0 GPUs are allocated
                        node_gpu_usage[node_name] = 0

        for node in result:
            node_name = node.get("HOSTNAMES") or node.get("node")
            # State
            state = node.get("STATE") or node.get("state", "Unknown")
            states[state] = states.get(state, 0) + 1

            # CPUs
            total_cpus += int(node.get("CPUS_TOTAL") or node.get("cpus_total", 0))
            idle_cpus += int(node.get("CPUS_IDLE") or node.get("cpus_idle", 0))

            # GPUs
            gres_gpu = node.get("GRES_GPU") or node.get("gres_gpu", "")
            if gres_gpu and ":" in gres_gpu:
                try:
                    gpu_count = int(gres_gpu.split(":")[-1])
                    total_gpus += gpu_count

                    # Calculate actual idle GPUs
                    if state.lower() == "idle":
                        current_idle_gpus = gpu_count
                    elif state.lower() == "mix":
                        used = node_gpu_usage.get(node_name, 0)
                        current_idle_gpus = max(0, gpu_count - used)
                    else:
                        current_idle_gpus = 0

                    idle_gpus += current_idle_gpus

                    # Feature-based GPU counts
                    features_str = node.get("ACTIVE_FEATURES") or node.get(
                        "active_features", ""
                    )
                    if features_str:
                        parts = [p.strip() for p in features_str.split(",")]
                        feature = parts[1] if len(parts) >= 2 else parts[0]

                        if feature:
                            if feature not in feature_gpus:
                                feature_gpus[feature] = {"total": 0, "idle": 0}
                            feature_gpus[feature]["total"] += gpu_count
                            feature_gpus[feature]["idle"] += current_idle_gpus
                except ValueError:
                    pass

        # Prepare state data for table
        state_data = [
            [s, c] for s, c in sorted(states.items(), key=lambda x: x[1], reverse=True)
        ]

        console.print("\n[bold]Cluster Summary[/bold]")
        console.print(f"  Total Nodes    : {total_nodes}")
        console.print(f"  Total CPUs     : {total_cpus}")
        console.print(f"  Idle CPUs      : {idle_cpus}")
        console.print(f"  Total GPUs     : {total_gpus}")
        console.print(f"  Idle GPUs      : {idle_gpus}")
        console.print()

        console.table(["State", "Count"], state_data, title="Node State Distribution")
        console.print()

        if feature_gpus:
            feature_data = [
                [f, d["total"], d["idle"]] for f, d in sorted(feature_gpus.items())
            ]
            console.table(
                ["Feature", "Total GPUs", "Idle GPUs"],
                feature_data,
                title="GPU Distribution by Active Feature",
            )
            console.print()
    elif output == "table":
        if query == "all":
            # Summary table for the detailed query
            header = ["Partition", "Node", "GRES", "State"]
            data = []
            for r in result:
                partition_val = r.get("PARTITION") or r.get("partition", "N/A")
                node_val = r.get("HOSTNAMES") or r.get("node", "N/A")
                gres_val = r.get("GRES") or r.get("gres", "N/A")
                state_val = r.get("STATE") or r.get("state", "N/A")
                data.append([partition_val, node_val, gres_val, state_val])
            console.table(header, data, title="Slurm Node Info Summary")
        else:
            if result and "raw" in result[0]:
                for row in result:
                    console.print(row["raw"])
            else:
                keys = list(result[0].keys())
                header = keys
                data = [[r.get(k, "N/A") for k in keys] for r in result]
                console.table(header, data, title="Slurm Node Info")
    elif output == "attributes":
        if query == "all":
            # Detailed key-value list
            for i, node_data in enumerate(result, 1):
                node_name = node_data.get("HOSTNAMES") or node_data.get(
                    "node", "Unknown Node"
                )
                console.print(f"\n[bold]Node {i}: {node_name}[/bold]")
                for key, value in node_data.items():
                    # GRES_SOCKET is already provided as a separate attribute by Slurm.sinfo
                    # We just print the attributes as they are.
                    console.print(f"  {key.ljust(20)} : {value}")
        else:
            for row in result:
                if "raw" in row:
                    console.print(row["raw"])
                else:
                    for k, v in row.items():
                        console.print(f"  {k.ljust(20)} : {v}")


@slurm_group.command(name="nodes")
@click.option("--partition", help="Partition to check")
def slurm_nodes(partition: Optional[str]) -> None:
    """Check node status for a partition."""
    hpc = Hpc()
    result = hpc.nodes(partition=partition)
    console.print(result)


@slurm_group.command(name="gpu-usage")
@click.argument("target", required=False)
@click.option("--cluster", is_flag=True, help="Show GPU usage for all nodes in the cluster (Heat Map)")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_gpu_usage(target: Optional[str], cluster: bool, debug: bool) -> None:
    """Find out how many GPUs on a particular host, reservation, or the whole cluster are used."""
    hpc = Hpc(debug=debug)

    if cluster:
        result = hpc.get_cluster_gpu_usage()
        if not result:
            console.error("Could not fetch cluster GPU usage.")
            return

        # Use a simpler printing method to avoid "Can't open" issues in some environments
        console.print("\n[bold]Cluster GPU Heat Map (Sorted by Availability)[/bold]")
        header = ["Node", "Partition", "Total", "Used", "Available", "State"]
        
        # Print header
        header_str = " | ".join([h.ljust(12) for h in header])
        console.print(header_str)
        console.print("-" * len(header_str))
        
        # Print rows
        for r in result:
            row = [r["node"], r["partition"], str(r["total"]), str(r["used"]), str(r["available"]), r["state"]]
            row_str = " | ".join([val.ljust(12) for val in row])
            console.print(row_str)
        console.print()
        return

    if not target:
        console.error("Please provide a target node/reservation or use --cluster.")
        return

    # Try as a node first
    result = hpc.get_node_gpu_usage(target)

    # If node lookup fails, try as a reservation
    if "error" in result:
        result = hpc.get_reservation_gpu_usage(target)

    if "error" in result:
        console.error(
            f"Could not find GPU usage for node or reservation '{target}': {result['error']}"
        )
        return

    label = (
        result.get("reservation")
        if "reservation" in result
        else result.get("node", target)
    )
    type_label = "Reservation" if "reservation" in result else "Node"

    console.print(f"\n[bold]{type_label} GPU Usage for {label}[/bold]")
    console.print(f"Total     : {result['total']}")
    console.print(f"Used      : {result['used']}")
    console.print(f"Available : {result['available']}")
    console.print()


@slurm_group.command(name="wait")
@click.argument("job_id")
@click.option("--interval", default=30, help="Polling interval in seconds")
def slurm_wait(job_id: str, interval: int) -> None:
    """Wait for a Slurm job to complete."""
    hpc = Hpc()
    hpc.wait(job_id, interval=interval)


@slurm_group.command(name="template")
@click.option("--key", help="Partition key for the template")
def slurm_template(key: Optional[str]) -> None:
    """Generate a boilerplate .sbatch script."""
    hpc = Hpc()
    result = hpc.template(key=key)
    console.print(result)


@slurm_group.command(name="run")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="hpc", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_run(
    sbatch: Optional[str], host: str, key: Optional[str], debug: bool
) -> None:
    """Runs a Slurm command."""
    hpc = Hpc(host=host, debug=debug)
    try:
        sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
    except ValueError as e:
        console.error(str(e))
        return
    hpc.login(host, key, sbatch_params=sbatch_params)


@slurm_group.command(name="cancel")
@click.argument("job_id")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_cancel(job_id: str, debug: bool) -> None:
    """Cancels a Slurm job."""
    hpc = Hpc(debug=debug)
    hpc.cancel(job_id)


@hpc_group.command(name="ticket")
@click.argument("target", required=False)
def hpc_ticket(target: Optional[str]) -> None:
    """Open a support request. Use 'www' for the web form, or leave blank for email."""
    hpc = Hpc()
    # Official UVA HPC RC Support email
    support_email = "hpc-support@virginia.edu"
    support_url = "https://www.rc.virginia.edu/form/support-request/"

    if target == "www":
        console.msg(f"Opening support web form: {support_url}")
        webbrowser.open(support_url)
    else:
        subject = "HPC Support Request"
        body = "Please describe your issue here."
        mailto_url = f"mailto:{support_email}?subject={subject}&body={body}"
        console.msg(f"Opening email client to: {support_email}")
        webbrowser.open(mailto_url)


@slurm_group.command(name="status")
@click.argument("job_id")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_status(job_id: str, debug: bool) -> None:
    """Gets the status of a specific Slurm job."""
    hpc = Hpc(debug=debug)
    result = hpc.get_job_status(job_id)
    console.print(result)


@slurm_group.command(name="list")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_list(debug: bool) -> None:
    """Lists all active Slurm jobs for the current user."""
    hpc = Hpc(debug=debug)
    result = hpc.list_jobs()
    console.print(result)

@slurm_group.command(name="monitor")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def slurm_monitor(ctx, debug: bool) -> None:
    """Interactively monitor Slurm jobs."""
    hpc = Hpc(debug=debug)
    app = JobMonitorApp(hpc)
    result = app.run()

    if not result:
        return

    if result.startswith("CANCEL:"):
        job_id = result.split(":", 1)[1]
        if questionary.confirm(f"Are you sure you want to cancel job {job_id}?").ask():
            hpc.cancel(job_id)
            console.msg(f"Job {job_id} cancelled.")
    else:
        # Result is a job_id, view logs
        ctx.invoke(slurm_logs, job_id=result, tail=False, follow=True)


@slurm_group.command(name="search-jobs")
@click.argument("node_regex")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_search_jobs(node_regex: str, debug: bool) -> None:
    """Find jobs running on nodes that match the given regex."""
    hpc = Hpc(debug=debug)
    result = hpc.search_jobs_by_node(node_regex)

    if not result:
        console.print(f"No jobs found running on nodes matching: {node_regex}")
        return

    header = ["User", "Job ID", "Node"]
    data = [[row["user"], row["job_id"], row["node"]] for row in result]

    console.table(header, data, title=f"Jobs on nodes matching: {node_regex}")


# --- Image Group ---
@hpc_group.group(name="image")
def image_group():
    """Image related commands."""
    pass


@image_group.command(name="build")
@click.argument("deffile")
def image_build(deffile: str) -> None:
    """Builds an image from a definition file."""
    hpc = Hpc()
    hpc.create_apptainer_image(deffile)


# --- Other Commands ---
class JobMonitorApp(App):
    """A Textual app to monitor Slurm jobs interactively."""

    CSS = """
    Screen {
        background: #f0f0f0;
        color: #333333;
    }
    DataTable {
        background: #ffffff;
        color: #333333;
        height: 1fr;
    }
    #details-panel {
        background: #e0e0e0;
        color: #333333;
        border: solid #cccccc;
        padding: 1;
        height: 10;
    }
    Footer {
        background: #000000;
        color: #ffffff;
    }
    """
    BINDINGS = [
        ("q", "quit", "- Quit"),
        ("l", "view_logs", "- View Logs"),
        ("c", "cancel_job", "- Cancel Job"),
        ("r", "refresh", "- Refresh List"),
    ]

    def __init__(self, hpc_instance):
        super().__init__()
        self.hpc = hpc_instance
        self.selected_job_id = None

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Static("Select a job to see details", id="details-panel")
        yield Footer()

    @work
    async def refresh_jobs(self) -> None:
        """Periodically refresh the job list."""
        while True:
            self.update_job_table()
            await asyncio.sleep(30)

    def update_job_table(self) -> None:
        table = self.query_one(DataTable)
        try:
            # Get jobs as a string from hpc.list_jobs()
            output = self.hpc.list_jobs()
            if not output or not output.strip():
                return

            lines = output.strip().split("\n")
            if len(lines) < 2:
                return

            # squeue output is typically fixed-width. 
            # We use split() for simplicity, but we must be careful with indices.
            header = lines[0].split()
            
            # Clear rows
            table.clear()
            
            # Only add columns if they haven't been added yet
            if not table.columns:
                table.add_columns(*header)
            
            for line in lines[1:]:
                row = line.split()
                if not row:
                    continue
                
                # In standard squeue, JOBID is the first column (index 0)
                job_id = row[0]
                table.add_row(*row, key=job_id)
        except Exception as e:
            self.query_one("#details-panel", Static).update(f"Error updating jobs: {e}")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        self.update_job_table()
        self.refresh_jobs()

    def on_data_table_row_selected(self, event) -> None:
        job_id = event.row_key.value if hasattr(event.row_key, "value") else event.row_key
        self.selected_job_id = job_id
        
        # Fetch detailed info
        info = self.hpc.job_info(job_id)
        self.query_one("#details-panel", Static).update(info)

    def action_view_logs(self) -> None:
        if not self.selected_job_id:
            return
        self.exit(self.selected_job_id)

    def action_cancel_job(self) -> None:
        if not self.selected_job_id:
            return
        # We exit with a special signal to indicate cancellation
        self.exit(f"CANCEL:{self.selected_job_id}")

    def action_refresh(self) -> None:
        self.update_job_table()

class PartitionSelectorApp(App):
    """A Textual app to select an HPC partition from a table."""

    CSS = """
    Screen {
        background: #f0f0f0;
        color: #333333;
    }
    DataTable {
        background: #ffffff;
        color: #333333;
    }
    DataTable > .dp-row {
        color: #333333;
    }
    DataTable > .dp-row:focus {
        background: #e0e0e0;
        color: #000000;
    }
    Footer {
        background: #dddddd;
        color: #333333;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("enter", "select", "Select"),
        ("d", "select_default", "Default"),
        ("+", "increase_gres", "Increase GPU"),
        ("-", "decrease_gres", "Decrease GPU"),
    ]

    def __init__(self, host, hpc_instance, header, choices):
        super().__init__()
        self.host = host
        self.hpc = hpc_instance
        self.header = header
        self.choices = choices
        self.selected_key = None
        self.default_key = self.hpc.get_default_partition(host)
        self.modified_sbatch_params = {}
        self.model = (
            {}
        )  # Stores {partition_key: {"row": [], "gres_count": int, "gres_prefix": str, "gres_idx": int}}

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Footer()

    def _update_gres(self, delta: int) -> None:
        table = self.query_one(DataTable)
        cursor_row_idx = table.cursor_row
        if cursor_row_idx is None:
            return

        try:
            # With explicit keys, row_key is the partition_key
            partition_key = table.rows[cursor_row_idx]
        except (IndexError, KeyError):
            return

        if partition_key not in self.model:
            return

        model_data = self.model[partition_key]
        gres_idx = model_data["gres_idx"]

        if gres_idx == -1:
            return

        # Update Model
        model_data["gres_count"] = max(1, model_data["gres_count"] + delta)

        # Assemble GRES string from model
        new_val = f"{model_data['gres_prefix']}{model_data['gres_count']}"
        model_data["row"][gres_idx] = new_val

        # Update View (DataTable)
        columns = [col.strip() for col in self.header.split(" | ")]
        if gres_idx < len(columns):
            gres_col_key = columns[gres_idx]
            table.update_cell(partition_key, gres_col_key, new_val)

        # Update modified params
        self.modified_sbatch_params[partition_key] = f"gres={new_val}"

    def action_increase_gres(self) -> None:
        self._update_gres(1)

    def action_decrease_gres(self) -> None:
        self._update_gres(-1)

    @work
    async def refresh_resources(self) -> None:
        """Asynchronously fetch and update real-time resource data periodically."""
        # Small delay to ensure the DataTable is fully mounted and rows are registered
        await asyncio.sleep(1.0)

        while True:
            # Fetch data from cluster in a separate thread to avoid blocking the event loop
            resource_map = await asyncio.to_thread(
                self.hpc.get_partition_realtime_data, self.host
            )
            if not resource_map:
                await asyncio.sleep(30)
                continue

            table = self.query_one(DataTable)
        columns = [col.strip() for col in self.header.split(" | ")]

        # Resource columns are the last two
        idle_col_idx = len(columns) - 2
        gpu_col_idx = len(columns) - 1
        idle_col_key = columns[idle_col_idx]
        gpu_col_key = columns[gpu_col_idx]

        # Iterate over model keys instead of table.rows for stability
        for partition_key in list(self.model.keys()):
            # Ensure the row is actually present in the table before updating
            if partition_key not in table.rows:
                continue

            # Get the actual Slurm partition name from the Hpc instance
            partition_name = (
                self.hpc.directive.get(self.host, {})
                .get(partition_key, {})
                .get("partition", "")
            )
            res = resource_map.get(partition_name)

            if res:
                nodes_str = f"{res['nodes']}/{res['total_nodes']}"
                gpus_str = f"{res['gpus']}/{res['used_gpus']}/{res['total_gpus']}"

                # Update View
                try:
                    table.update_cell(partition_key, idle_col_key, nodes_str)
                    table.update_cell(partition_key, gpu_col_key, gpus_str)
                except Exception:
                    # If the cell isn't ready yet, we skip this update
                    pass

                # Update Model
                if partition_key in self.model:
                    self.model[partition_key]["row"][idle_col_idx] = nodes_str
                    self.model[partition_key]["row"][gpu_col_idx] = gpus_str

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"

        # Setup columns using pre-fetched header, stripping whitespace for clean keys
        columns = [col.strip() for col in self.header.split(" | ")]
        table.add_columns(*columns)

        # Find GRES column index
        gres_col_idx = -1
        for i, col in enumerate(columns):
            if "gres" in col.lower():
                gres_col_idx = i
                break

        # Populate model and table
        for choice in self.choices:
            partition_key = choice["value"]
            row_data = choice["name"].split(" | ")

            gres_prefix = ""
            gres_count = 0
            if gres_col_idx != -1 and gres_col_idx < len(row_data):
                val = row_data[gres_col_idx].strip()
                import re

                match = re.search(r"(\d+)$", val)
                if match:
                    gres_count = int(match.group(1))
                    gres_prefix = val[: match.start()]
                else:
                    gres_prefix = val

            self.model[partition_key] = {
                "row": row_data,
                "gres_count": gres_count,
                "gres_prefix": gres_prefix,
                "gres_idx": gres_col_idx,
            }
            # Use partition_key as the explicit row key
            table.add_row(*row_data, key=partition_key)

        # Start asynchronous resource refresh
        self.refresh_resources()

    def on_data_table_row_selected(self, event) -> None:
        # With explicit keys, event.row_key is a RowKey object; we need its .value
        partition_key = (
            event.row_key.value if hasattr(event.row_key, "value") else event.row_key
        )
        self.selected_key = partition_key
        self.exit((self.selected_key, self.modified_sbatch_params))

    def action_select(self) -> None:
        table = self.query_one(DataTable)
        cursor_row_idx = table.cursor_row
        if cursor_row_idx is not None:
            # With explicit keys, table.rows[idx] is a RowKey object; we need its .value
            row_key = table.rows[cursor_row_idx]
            partition_key = row_key.value if hasattr(row_key, "value") else row_key
            self.selected_key = partition_key
            self.exit((self.selected_key, self.modified_sbatch_params))

    def action_select_default(self) -> None:
        """Select the default partition."""
        if not self.default_key:
            return

        table = self.query_one(DataTable)
        for row_key in table.rows:
            # Use the explicit key if available
            rk_val = row_key.value if hasattr(row_key, "value") else row_key
            if rk_val == self.default_key:
                self.selected_key = self.default_key
                self.exit((self.selected_key, self.modified_sbatch_params))
                break

            # Fallback to checking the second column
            row_data = table.get_row(row_key)
            if len(row_data) > 1 and row_data[1].strip() == self.default_key:
                self.selected_key = self.default_key
                self.exit((self.selected_key, self.modified_sbatch_params))
                break


@hpc_group.command(name="login")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="hpc", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--ui", is_flag=True, help="Use interactive UI to select partition")
def login_cmd(
    sbatch: Optional[str], host: str, key: Optional[str], debug: bool, ui: bool
) -> None:
    """Logs into an interactive node on HPC."""
    # Resolve host: if it's the default "hpc", use the Hpc class default (e.g., "uva")
    actual_host = host
    if host == "hpc":
        hpc_temp = Hpc()
        actual_host = hpc_temp.host

    hpc = Hpc(host=actual_host, debug=debug)

    if ui:
        try:
            # Fetch static table data (fast)
            header, choices = hpc.get_partition_static_data(actual_host)
            if not header or not choices:
                console.error("Could not fetch partition data.")
                return

            # Use Textual app for partition selection
            app = PartitionSelectorApp(actual_host, hpc, header, choices)
            result = app.run()

            if not result:
                console.warning("No partition selected. Exiting.")
                return

            selected_key, modified_params = result

            # Construct the command that will be executed
            cmd_parts = ["cmc hpc login"]
            if host != "hpc":
                cmd_parts.append(f"--host {host}")
            if sbatch:
                cmd_parts.append(f'--sbatch "{sbatch}"')
            cmd_parts.append(selected_key)
            full_cmd = " ".join(cmd_parts)

            # Check resource availability before proceeding
            console.print("\n[bold]Checking resource availability...[/bold]")
            availability = hpc.check_resource_availability(selected_key)
            if "error" in availability:
                console.error(f"Could not check resources: {availability['error']}")
            else:
                idle_count = availability["idle_nodes"]
                total_count = availability["total_nodes"]
                console.print(f"Partition: {availability['partition']}")
                console.print(f"Nodes: {idle_count}/{total_count} idle")

                if idle_count > 0:
                    console.print("[green]✓ Available resources found.[/green]")
                    # Show the first few idle nodes and their GPUs
                    for node in availability["idle_details"][:3]:
                        console.print(
                            f"  - {node['node']}: {node['gres']} ({node['state']})"
                        )
                    if len(availability["idle_details"]) > 3:
                        console.print(
                            f"  ... and {len(availability['idle_details']) - 3} more."
                        )
                else:
                    console.print(
                        "[yellow]⚠ No completely idle nodes found. Your job may be queued.[/yellow]"
                    )
                console.print()

            # Get the actual ijob command that will be run
            sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
            if sbatch_params is None:
                sbatch_params = {}

            # Merge modified params from UI
            if modified_params:
                # The modified_params are stored as {key: "gres=val"}
                # We only care about the one for the selected_key
                if selected_key in modified_params:
                    gres_val = modified_params[selected_key]
                    k, v = gres_val.split("=")
                    sbatch_params[k] = v

            ijob_cmd = hpc.get_login_command(actual_host, selected_key, sbatch_params)

            # Present the command in a banner
            banner_content = f"# {full_cmd}\n{ijob_cmd}"
            console.banner("Interactive Job", banner_content)

            # Confirmation Step using questionary
            confirmed = questionary.confirm(
                f"Do you want to start the login process?", default=True
            ).ask()

            if not confirmed:
                console.msg("Login cancelled by user.")
                return

            key = selected_key

        except KeyboardInterrupt:
            console.msg("\nLogin cancelled by user (Ctrl+C).")
            return

    try:
        sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
    except ValueError as e:
        console.error(str(e))
        return
    hpc.login(actual_host, key, sbatch_params=sbatch_params)


@hpc_group.command(name="tutorial")
@click.argument("keyword", required=False)
def tutorial_cmd(keyword: Optional[str]) -> None:
    """Shows HPC tutorials based on keyword."""
    hpc = Hpc()
    url = hpc.get_tutorial_url(keyword)
    console.msg(f"Opening tutorial for {keyword or 'general'}: {url}")
    webbrowser.open(url)




@hpc_group.command(name="jupyter")
@click.option("--port", default=8000, help="Port for Jupyter")
def jupyter_cmd(port: int) -> None:
    """Starts a Jupyter notebook."""
    hpc = Hpc()
    hpc.jupyter(port)


@hpc_group.command(name="edit")
@click.argument("filename")
@click.option("--editor", default="emacs", help="Editor to use")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def edit_cmd(filename: str, editor: str, debug: bool) -> None:
    """Edits a file on HPC."""
    hpc = Hpc(debug=debug)
    hpc.edit(filename, editor)


@hpc_group.command(name="set-default")
@click.option("--host", required=True, help="Default host to use")
@click.option("--partition", help="Default partition key to use")
def set_default_cmd(host: str, partition: Optional[str]) -> None:
    """Set the default host and partition for future commands."""
    hpc = Hpc()
    hpc.set_default(host, partition)


@hpc_group.command(name="config")
def config_cmd() -> None:
    """Prints the hardware and queue configuration for HPC."""

    hpc = Hpc()
    config_path = hpc.get_config_path()

    if not os.path.exists(config_path):
        console.error(f"Configuration file not found: {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    sections = {}
    current_section = None
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    def print_table(title, header, data, link):
        # Use the simplified console.table for the main display
        console.table(header, data, title=title)
        console.print(f"[link={link}]Source: {link}[/link]\n")

    if "Hardware" in sections:
        hw_lines = sections["Hardware"]
        if hw_lines:
            header = []
            for h in hw_lines[0].split(","):
                # Split by slash
                h = re.sub(r"\s*/\s*", "\n/", h)
                # Specifically split "Specialty Hardware"
                if h == "Specialty Hardware":
                    h = "Specialty\nHardware"
                header.append(h)
            data = [line.split(",") for line in hw_lines[1:]]
            console.banner(
                "HPC Hardware Configuration",
                "Detailed hardware specifications for the HPC cluster.",
            )
            print_table(
                "Hardware Configuration",
                header,
                data,
                "https://www.rc.virginia.edu/userinfo/hpc/#hardware-configuration",
            )

    if "Queues" in sections:
        q_lines = sections["Queues"]
        if q_lines:
            header = [re.sub(r"\s*/\s*", "\n/", h) for h in q_lines[0].split(",")]
            data = [line.split(",") for line in q_lines[1:]]
            console.banner(
                "HPC Queue Configuration",
                "Available Slurm queues and their constraints.",
            )
            print_table(
                "Queues",
                header,
                data,
                "https://www.rc.virginia.edu/userinfo/hpc/#job-queues",
            )


@hpc_group.command(name="check")
def check_cmd() -> None:
    """Perform a health check of the HPC environment (VPN, SSH, Quota)."""
    hpc = Hpc()
    hpc.check()

@hpc_group.command(name="info")
@click.argument("key", required=False)
def info_cmd(key: Optional[str]) -> None:
    """Prints information about the current HPC configuration or a specific partition."""
    hpc = Hpc()

    # 1. If no key provided, show default host info
    if not key:
        host = hpc.host
        default_partition = hpc.get_default_partition(host)
        available_hosts = list(hpc.directive.keys())
        console.print("\n[bold]HPC Configuration Info[/bold]")
        console.print(f"Current Host      : {host}")
        console.print(f"Default Partition : {default_partition or 'Not set'}")
        console.print(f"Available Hosts   : {', '.join(available_hosts)}")
        console.print("")

        header, data = hpc.get_partition_data(host)
        if header and data:
            console.table(header, data, title="Partitions")
        return

    # 2. Check if the key is a top-level host
    if key in hpc.directive:
        host = key
        default_partition = hpc.get_default_partition(host)
        available_hosts = list(hpc.directive.keys())
        console.print("\n[bold]HPC Host Info[/bold]")
        console.print(f"Host              : {host}")
        console.print(f"Default Partition : {default_partition or 'Not set'}")
        console.print(f"Available Hosts   : {', '.join(available_hosts)}")

        header, data = hpc.get_partition_data(host)
        if header and data:
            console.table(header, data, title="Partitions")
        return

    # 3. Check if the key is a partition key for any host
    for host, partitions in hpc.directive.items():
        if key in partitions:
            directives = partitions[key]
            console.print("\n[bold]HPC Partition Info[/bold]")
            console.print(f"Host       : {host}")
            console.print(f"Partition  : {key}")
            for k, v in directives.items():
                console.print(f"{k.ljust(12)} : {v}")
            console.print()
            return

    # 4. Not found
    # Try to suggest a match from hosts or any partition key
    all_hosts = list(hpc.directive.keys())
    all_partitions = []
    for p in hpc.directive.values():
        all_partitions.extend(list(p.keys()))

    suggestion = hpc._suggest_match(key, all_hosts + all_partitions)

    msg = f"Key '{key}' not found as a host or partition key."
    if suggestion:
        msg += f"\nDid you mean '{suggestion}'?"

    console.error(msg)
    # Fallback to default info
    host = hpc.host
    console.print(f"\nDefault Host: {host}")


def register(cli: Any) -> None:
    cli.add_command(hpc_group, name="hpc")

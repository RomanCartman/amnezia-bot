import asyncio
import logging

logger = logging.getLogger(__name__)


async def generate_vpn_key(conf_path: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "python3.11",
        "awg-decode.py",
        "--encode",
        conf_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return (
        stdout.decode().strip()
        if process.returncode == 0 and stdout.decode().startswith("vpn://")
        else ""
    )

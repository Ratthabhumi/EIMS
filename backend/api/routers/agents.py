import os
import subprocess
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/agents", tags=["Client Agents"])

class AgentLaunchRequest(BaseModel):
    agent_name: str

@router.post("/launch", status_code=status.HTTP_200_OK)
async def launch_agent(request: AgentLaunchRequest):
    """
    Launches a local EIMS Desktop Agent. 
    Only works if the backend is running on the local Windows machine.
    """
    # Define absolute paths based on project root
    # Since backend is in backend/, the project root is one level up
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    
    agent_paths = {
        "usb_auditor": os.path.join(base_dir, "clients", "usb_auditor", "run.bat"),
        "sticker_ocr": os.path.join(base_dir, "clients", "sticker_ocr", "run.bat")
    }

    target_bat = agent_paths.get(request.agent_name)

    if not target_bat:
        raise HTTPException(status_code=400, detail="Unknown agent name.")

    if not os.path.exists(target_bat):
        raise HTTPException(status_code=404, detail=f"Agent batch file not found at {target_bat}")

    try:
        # Launch the batch file in a new detached console window
        subprocess.Popen(
            f'start "" "{target_bat}"',
            shell=True,
            cwd=os.path.dirname(target_bat)
        )
        return {"status": "success", "message": f"{request.agent_name} launched successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

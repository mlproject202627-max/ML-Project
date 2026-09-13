from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import csv
import io

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.activity import Activity
from app.schemas.activity import ActivityIngestRequest

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


@router.post("/activities")
def ingest_activities(
    activities: List[ActivityIngestRequest],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Ingest a batch of activity events."""
    records_received = len(activities)
    records_imported = 0
    records_rejected = 0
    validation_errors = []
    
    for i, activity_data in enumerate(activities):
        try:
            # Validate user exists
            user = db.query(User).filter(User.id == activity_data.user_id).first()
            if not user:
                validation_errors.append({
                    "row": i + 1,
                    "error": f"User {activity_data.user_id} not found"
                })
                records_rejected += 1
                continue
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(activity_data.timestamp)
            except ValueError:
                validation_errors.append({
                    "row": i + 1,
                    "error": f"Invalid timestamp format: {activity_data.timestamp}"
                })
                records_rejected += 1
                continue
            
            activity = Activity(
                user_id=activity_data.user_id,
                timestamp=timestamp,
                event_type=activity_data.event_type,
                action=activity_data.action,
                resource=activity_data.resource,
                source_ip=activity_data.source_ip,
                device=activity_data.device,
                location=activity_data.location,
                application=activity_data.application,
                metadata=activity_data.metadata or {},
            )
            db.add(activity)
            records_imported += 1
            
        except Exception as e:
            validation_errors.append({
                "row": i + 1,
                "error": str(e)
            })
            records_rejected += 1
    
    db.commit()
    
    return {
        "records_received": records_received,
        "records_imported": records_imported,
        "records_rejected": records_rejected,
        "validation_errors": validation_errors,
    }


@router.post("/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Ingest activity data from a CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    text = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    
    records_received = 0
    records_imported = 0
    records_rejected = 0
    validation_errors = []
    
    required_columns = ['user_id', 'timestamp', 'event_type', 'action']
    
    if not all(col in (reader.fieldnames or []) for col in required_columns):
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns. Required: {required_columns}"
        )
    
    for i, row in enumerate(reader):
        records_received += 1
        try:
            user = db.query(User).filter(User.id == row['user_id']).first()
            if not user:
                validation_errors.append({"row": i + 2, "error": f"User {row['user_id']} not found"})
                records_rejected += 1
                continue
            
            try:
                timestamp = datetime.fromisoformat(row['timestamp'])
            except ValueError:
                validation_errors.append({"row": i + 2, "error": f"Invalid timestamp: {row['timestamp']}"})
                records_rejected += 1
                continue
            
            activity = Activity(
                user_id=row['user_id'],
                timestamp=timestamp,
                event_type=row['event_type'],
                action=row['action'],
                resource=row.get('resource'),
                source_ip=row.get('source_ip'),
                device=row.get('device'),
                location=row.get('location'),
                application=row.get('application'),
            )
            db.add(activity)
            records_imported += 1
            
        except Exception as e:
            validation_errors.append({"row": i + 2, "error": str(e)})
            records_rejected += 1
    
    db.commit()
    
    return {
        "records_received": records_received,
        "records_imported": records_imported,
        "records_rejected": records_rejected,
        "validation_errors": validation_errors,
    }

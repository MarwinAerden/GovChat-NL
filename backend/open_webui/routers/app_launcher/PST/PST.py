"""
PST Parser Router for OpenWebUI App Launcher

Based on concepts from XstReader (https://github.com/iluvadev/XstReader)
This module provides PST file parsing capabilities for email analysis and extraction.

Installation requirements:
- pypff (libpff-python): pip install libpff-python
- Or install all requirements: pip install -r requirements.txt

Note: libpff-python may require additional system dependencies on Linux/macOS.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import tempfile
import os
import io
import json
from datetime import datetime
import logging

# We'll need to install these Python libraries for PST parsing
try:
    import pypff  # Python library for PST file parsing
except ImportError:
    # Fallback for when pypff is not available
    pypff = None

from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel


router = APIRouter()


class PSTFileInfo(BaseModel):
    """Model for PST file information"""
    filename: str
    size: int
    created_time: Optional[str] = None  # Changed to string for JSON serialization
    modified_time: Optional[str] = None  # Changed to string for JSON serialization
    folder_count: int = 0
    message_count: int = 0


class PSTFolder(BaseModel):
    """Model for PST folder structure"""
    name: str
    path: str
    sub_folders: List[Dict[str, Any]] = []  # Changed to Dict to avoid recursive issues
    message_count: int = 0
    folder_type: Optional[str] = None


class PSTMessage(BaseModel):
    """Model for PST message/email"""
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipients: List[str] = []
    sent_time: Optional[str] = None  # Changed to string for JSON serialization
    received_time: Optional[str] = None  # Changed to string for JSON serialization
    body_plain: Optional[str] = None
    body_html: Optional[str] = None
    has_attachments: bool = False
    attachment_count: int = 0
    message_size: int = 0
    folder_path: str = ""


class PSTAttachment(BaseModel):
    """Model for PST attachment"""
    filename: str
    size: int
    content_type: Optional[str] = None
    is_inline: bool = False


class PSTAnalysisRequest(BaseModel):
    """Request model for PST analysis"""
    file_path: str
    include_body: bool = True
    max_messages: Optional[int] = None
    folder_filter: Optional[str] = None
    selected_folders: Optional[List[str]] = None  # List of folder paths to analyze


class PSTSearchRequest(BaseModel):
    """Request model for PST search"""
    file_path: str
    query: str
    search_in: List[str] = ["subject", "body", "sender"]  # subject, body, sender, recipients
    date_from: Optional[str] = None  # Changed to string for JSON serialization
    date_to: Optional[str] = None  # Changed to string for JSON serialization
    folder_path: Optional[str] = None
    selected_folders: Optional[List[str]] = None  # List of folder paths to search in


def safe_datetime_to_string(dt) -> Optional[str]:
    """Convert datetime to ISO string safely"""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def safe_bytes_to_string(data) -> Optional[str]:
    """Convert bytes data to string safely"""
    if data is None:
        return None
    if isinstance(data, bytes):
        try:
            # Try UTF-8 first
            return data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Try latin-1 as fallback
                return data.decode('latin-1')
            except UnicodeDecodeError:
                # Last resort - ignore errors
                return data.decode('utf-8', errors='ignore')
    return str(data)


def check_pypff_available():
    """Check if pypff library is available"""
    if pypff is None:
        raise HTTPException(
            status_code=500,
            detail="PST parsing library (pypff) is not installed. Please install libpff-python package."
        )


def parse_pst_file(file_path: str) -> Dict[str, Any]:
    """
    Parse PST file and extract basic information
    
    Args:
        file_path: Path to the PST file
        
    Returns:
        Dictionary containing PST file information
    """
    check_pypff_available()
    
    try:
        # Open PST file
        pst_file = pypff.file()
        pst_file.open(file_path)
        
        # Get root folder
        root_folder = pst_file.get_root_folder()
        
        # Count folders recursively
        folder_count = count_folders_recursive(root_folder)
        
        # Get basic file info
        total_messages = calculate_total_messages(root_folder)
        
        file_info = PSTFileInfo(
            filename=os.path.basename(file_path),
            size=os.path.getsize(file_path),
            created_time=safe_datetime_to_string(datetime.fromtimestamp(os.path.getctime(file_path))),
            modified_time=safe_datetime_to_string(datetime.fromtimestamp(os.path.getmtime(file_path))),
            folder_count=folder_count,
            message_count=total_messages
        )
        
        # Parse folder structure (both flat and hierarchical)
        folders_flat = parse_folder_structure(root_folder)
        folders_hierarchical = parse_folder_structure_hierarchical(root_folder)
        
        pst_file.close()
        
        return {
            "file_info": file_info.dict(),
            "folders": folders_flat,
            "folders_hierarchical": folders_hierarchical,
            "total_folders": len(folders_flat)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing PST file: {str(e)}")


def count_folders_recursive(folder) -> int:
    """
    Recursively count all folders
    
    Args:
        folder: pypff folder object
        
    Returns:
        Total number of folders
    """
    if not folder:
        return 0
    
    count = 1  # Count current folder
    
    try:
        # Get number of sub-folders using pypff API
        num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
        logging.debug(f"Folder '{safe_bytes_to_string(getattr(folder, 'name', 'Unknown'))}' has {num_sub_folders} sub-folders")
        
        for i in range(num_sub_folders):
            try:
                sub_folder = folder.get_sub_folder(i)
                if sub_folder:
                    count += count_folders_recursive(sub_folder)
                else:
                    logging.warning(f"Sub-folder {i} is None")
            except Exception as e:
                logging.warning(f"Error accessing sub-folder {i}: {str(e)}")
                continue
    except Exception as e:
        logging.error(f"Error counting folders: {str(e)}")
    
    return count


def parse_folder_structure(folder, path="") -> List[Dict[str, Any]]:
    """
    Recursively parse folder structure
    
    Args:
        folder: pypff folder object
        path: Current folder path
        
    Returns:
        List of folder dictionaries (flattened list of all folders)
    """
    folders = []
    
    try:
        # Get folder name using pypff API
        folder_name = safe_bytes_to_string(getattr(folder, 'name', None)) or "Unknown"
        current_path = f"{path}/{folder_name}" if path else folder_name
        
        # Get message count
        message_count = getattr(folder, 'number_of_sub_messages', 0)
        
        folder_info = PSTFolder(
            name=folder_name,
            path=current_path,
            message_count=safe_get_message_count(folder),
            folder_type=get_folder_type(folder),
            sub_folders=[]  # Will be populated with sub-folder data, not recursive structure
        )
        
        # Add current folder to the list
        folders.append(folder_info.model_dump())
        
        # Parse sub-folders using pypff API and add them to the flat list
        try:
            num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
            sub_folder_list = []
            
            for i in range(num_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    sub_folder_name = safe_bytes_to_string(getattr(sub_folder, 'name', None)) or f"SubFolder_{i}"
                    sub_folder_path = f"{current_path}/{sub_folder_name}"
                    
                    # Add basic sub-folder info to current folder's sub_folders list
                    sub_folder_list.append({
                        "name": sub_folder_name,
                        "path": sub_folder_path,
                        "message_count": safe_get_message_count(sub_folder),
                        "folder_type": get_folder_type(sub_folder)
                    })
                    
                    # Recursively parse sub-folders and add them to the main list
                    sub_folder_data = parse_folder_structure(sub_folder, current_path)
                    folders.extend(sub_folder_data)
                    
                except Exception as e:
                    logging.warning(f"Error parsing sub-folder {i} in {current_path}: {str(e)}")
                    continue
                    
            # Update current folder's sub_folders list
            if folders:
                folders[0]["sub_folders"] = sub_folder_list
                
        except Exception as e:
            logging.error(f"Error iterating sub-folders in {current_path}: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error parsing folder {path}: {str(e)}")
    
    return folders


def parse_folder_structure_hierarchical(folder, path="") -> Dict[str, Any]:
    """
    Parse folder structure maintaining hierarchy
    
    Args:
        folder: pypff folder object
        path: Current folder path
        
    Returns:
        Dictionary representing the folder hierarchy
    """
    try:
        # Get folder name using pypff API
        folder_name = safe_bytes_to_string(getattr(folder, 'name', None)) or "Unknown"
        current_path = f"{path}/{folder_name}" if path else folder_name
        
        # Get message count
        message_count = getattr(folder, 'number_of_sub_messages', 0)
        
        folder_info = {
            "name": folder_name,
            "path": current_path,
            "message_count": safe_get_message_count(folder),
            "folder_type": get_folder_type(folder),
            "sub_folders": []
        }
        
        # Parse sub-folders using pypff API
        try:
            num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
            for i in range(num_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    sub_folder_info = parse_folder_structure_hierarchical(sub_folder, current_path)
                    folder_info["sub_folders"].append(sub_folder_info)
                except Exception as e:
                    logging.warning(f"Error parsing sub-folder {i} hierarchically in {current_path}: {str(e)}")
                    continue
        except Exception as e:
            logging.error(f"Error iterating sub-folders hierarchically in {current_path}: {str(e)}")
        
        return folder_info
        
    except Exception as e:
        logging.error(f"Error parsing folder hierarchically {path}: {str(e)}")
        return {
            "name": "Error",
            "path": path,
            "message_count": 0,
            "folder_type": "error",
            "sub_folders": []
        }


def get_folder_type(folder) -> str:
    """
    Determine folder type based on folder properties
    
    Args:
        folder: pypff folder object
        
    Returns:
        String indicating folder type
    """
    try:
        # This is a simplified implementation
        # In reality, you'd check specific MAPI properties
        name = (getattr(folder, 'name', '') or "").lower()
        
        if 'inbox' in name or 'postvak in' in name:
            return 'inbox'
        elif 'sent' in name or 'verzonden' in name:
            return 'sent'
        elif 'draft' in name or 'concept' in name:
            return 'drafts'
        elif 'deleted' in name or 'trash' in name or 'verwijderd' in name:
            return 'deleted'
        elif 'junk' in name or 'spam' in name or 'ongewenst' in name:
            return 'junk'
        elif 'outbox' in name or 'postvak uit' in name:
            return 'outbox'
        else:
            return 'regular'
            
    except:
        return 'unknown'


def extract_messages_from_folder(folder, max_messages=None, include_body=True) -> List[Dict[str, Any]]:
    """
    Extract messages from a specific folder
    
    Args:
        folder: pypff folder object
        max_messages: Maximum number of messages to extract
        include_body: Whether to include message body
        
    Returns:
        List of message dictionaries
    """
    messages = []
    count = 0
    
    try:
        # Get number of messages using pypff API
        num_messages = getattr(folder, 'number_of_sub_messages', 0)
        
        for i in range(num_messages):
            if max_messages and count >= max_messages:
                break
                
            try:
                message = folder.get_sub_message(i)
                
                # Safely extract attachment information
                has_attachments, attachment_count = safe_extract_attachments(message)
                
                msg_info = PSTMessage(
                    subject=safe_bytes_to_string(getattr(message, 'subject', None)),
                    sender=safe_bytes_to_string(getattr(message, 'sender_name', None)),
                    recipients=[],  # Will be populated below
                    sent_time=safe_datetime_to_string(getattr(message, 'creation_time', None)),
                    received_time=safe_datetime_to_string(getattr(message, 'delivery_time', None)),
                    has_attachments=has_attachments,
                    attachment_count=attachment_count,
                    message_size=getattr(message, 'size', 0),
                    folder_path=getattr(folder, 'name', '') or "Unknown"
                )
                
                # Extract recipients
                recipients = []
                try:
                    num_recipients = getattr(message, 'number_of_recipients', 0)
                    for j in range(num_recipients):
                        try:
                            recipient = message.get_recipient(j)
                            email = safe_bytes_to_string(getattr(recipient, 'email_address', None))
                            name = safe_bytes_to_string(getattr(recipient, 'name', None))
                            if email:
                                recipients.append(f"{name} <{email}>" if name else email)
                        except Exception as e:
                            logging.warning(f"Error reading recipient {j}: {str(e)}")
                            continue
                except Exception as e:
                    logging.warning(f"Error reading recipients: {str(e)}")
                    
                msg_info.recipients = recipients
                
                # Extract body if requested
                if include_body:
                    try:
                        # Get plain text body and ensure it's a string
                        plain_body = getattr(message, 'plain_text_body', None)
                        msg_info.body_plain = safe_bytes_to_string(plain_body)
                        
                        # Get HTML body and ensure it's a string
                        html_body = getattr(message, 'html_body', None)
                        msg_info.body_html = safe_bytes_to_string(html_body)
                    except Exception as e:
                        logging.warning(f"Error reading message body: {str(e)}")
                        msg_info.body_plain = None
                        msg_info.body_html = None
                
                messages.append(msg_info.model_dump())
                count += 1
                
            except Exception as e:
                logging.warning(f"Error extracting message {i}: {str(e)}")
                continue
                
    except Exception as e:
        logging.error(f"Error iterating messages: {str(e)}")
    
    return messages


def safe_extract_attachments(message) -> tuple[bool, int]:
    """
    Safely extract attachment information from a message
    
    Args:
        message: pypff message object
        
    Returns:
        Tuple of (has_attachments, attachment_count)
    """
    try:
        # Try to get attachment count
        attachment_count = getattr(message, 'number_of_attachments', 0)
        if attachment_count is None:
            attachment_count = 0
            
        has_attachments = attachment_count > 0
        
        # If we have attachments, try to verify we can access them
        if has_attachments:
            try:
                # Try to access the first attachment to verify they're readable
                if hasattr(message, 'get_attachment'):
                    test_attachment = message.get_attachment(0)
                    if test_attachment is None:
                        # Attachments exist but can't be read - treat as no attachments
                        logging.warning("Attachments exist but cannot be accessed due to libpff limitations")
                        has_attachments = False
                        attachment_count = 0
            except Exception as e:
                # Common libpff error: local descriptor identifier not found
                if "local descriptor identifier" in str(e).lower():
                    logging.warning(f"Attachment access blocked by libpff local descriptor error: {str(e)}")
                    has_attachments = False
                    attachment_count = 0
                else:
                    logging.warning(f"Error verifying attachment access: {str(e)}")
                    # Keep original counts but log the issue
        
        return has_attachments, attachment_count
        
    except Exception as e:
        logging.warning(f"Error extracting attachment info: {str(e)}")
        return False, 0


@router.post("/upload")
async def upload_pst_file(
    file: UploadFile = File(...),
    user: UserModel = Depends(get_verified_user)
):
    """
    Upload and parse a PST file
    """
    if not file.filename.lower().endswith(('.pst', '.ost')):
        raise HTTPException(status_code=400, detail="Only PST and OST files are supported")
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pst") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        # Parse the PST file
        result = parse_pst_file(temp_file_path)
        result["temp_file_path"] = temp_file_path  # Store for later use
        
        return JSONResponse(content=result)
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        raise e


@router.post("/analyze")
async def analyze_pst_file(
    request: PSTAnalysisRequest,
    user: UserModel = Depends(get_verified_user)
):
    """
    Analyze PST file and extract detailed information
    """
    check_pypff_available()
    
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="PST file not found")
    
    try:
        pst_file = pypff.file()
        pst_file.open(request.file_path)
        
        result = {
            "analysis_started": safe_datetime_to_string(datetime.now()),
            "messages": [],
            "summary": {
                "total_messages": 0,
                "total_attachments": 0,
                "date_range": {"earliest": None, "latest": None},
                "top_senders": {},
                "folder_distribution": {}
            }
        }
        
        # Analyze each folder using new selection-aware function
        root_folder = pst_file.get_root_folder()
        
        if request.selected_folders:
            logging.info(f"Analyzing selected folders: {request.selected_folders}")
            messages = analyze_folder_recursive_with_selection(root_folder, request)
        else:
            # Fall back to old method for backward compatibility
            messages = analyze_folder_recursive(
                root_folder, 
                request.max_messages, 
                request.include_body,
                request.folder_filter
            )
        
        result["messages"] = messages
        result["summary"]["total_messages"] = len(messages)
        
        # Calculate summary statistics
        if messages:
            dates = [msg.get("sent_time") for msg in messages if msg.get("sent_time")]
            if dates:
                result["summary"]["date_range"]["earliest"] = min(dates)
                result["summary"]["date_range"]["latest"] = max(dates)
        
        pst_file.close()
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing PST file: {str(e)}")


def analyze_folder_recursive(folder, max_messages=None, include_body=True, folder_filter=None) -> List[Dict[str, Any]]:
    """
    Recursively analyze all folders and extract messages
    """
    all_messages = []
    
    try:
        # Check if this folder matches filter
        folder_name = getattr(folder, 'name', '') or "Unknown"
        if folder_filter and folder_filter.lower() not in folder_name.lower():
            # Still check sub-folders
            try:
                num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
                for i in range(num_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        sub_messages = analyze_folder_recursive(sub_folder, max_messages, include_body, folder_filter)
                        all_messages.extend(sub_messages)
                        if max_messages and len(all_messages) >= max_messages:
                            break
                    except Exception as e:
                        logging.warning(f"Error analyzing sub-folder {i}: {str(e)}")
                        continue
            except Exception as e:
                logging.error(f"Error iterating sub-folders: {str(e)}")
        else:
            # Extract messages from current folder
            folder_messages = extract_messages_from_folder(folder, max_messages, include_body)
            all_messages.extend(folder_messages)
            
            # Process sub-folders
            if not max_messages or len(all_messages) < max_messages:
                try:
                    num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
                    for i in range(num_sub_folders):
                        try:
                            sub_folder = folder.get_sub_folder(i)
                            remaining = max_messages - len(all_messages) if max_messages else None
                            sub_messages = analyze_folder_recursive(sub_folder, remaining, include_body, folder_filter)
                            all_messages.extend(sub_messages)
                            if max_messages and len(all_messages) >= max_messages:
                                break
                        except Exception as e:
                            logging.warning(f"Error analyzing sub-folder {i}: {str(e)}")
                            continue
                except Exception as e:
                    logging.error(f"Error iterating sub-folders: {str(e)}")
    
    except Exception as e:
        logging.error(f"Error in recursive analysis: {str(e)}")
    
    return all_messages


def analyze_folder_recursive_with_selection(folder, request, current_path="", processed_folders=None) -> List[Dict[str, Any]]:
    """
    Recursively analyze folders based on selection criteria
    
    Args:
        folder: pypff folder object
        request: PSTAnalysisRequest object with selection criteria
        current_path: Current folder path for tracking
        processed_folders: Set of already processed folder paths
        
    Returns:
        List of message dictionaries
    """
    if processed_folders is None:
        processed_folders = set()
    
    all_messages = []
    
    try:
        # Get folder name and build current path
        folder_name = safe_bytes_to_string(getattr(folder, 'name', '')) or "Unknown"
        if current_path:
            full_path = f"{current_path}/{folder_name}"
        else:
            full_path = folder_name
        
        # Avoid processing the same folder twice
        if full_path in processed_folders:
            return all_messages
        processed_folders.add(full_path)
        
        # Check if this folder should be analyzed
        if should_analyze_folder(folder, full_path, request):
            logging.info(f"Analyzing selected folder: {full_path}")
            
            # Extract messages from current folder
            folder_messages = extract_messages_from_folder(
                folder, 
                request.max_messages - len(all_messages) if request.max_messages else None,
                request.include_body
            )
            all_messages.extend(folder_messages)
            
            # Stop if we've reached the message limit
            if request.max_messages and len(all_messages) >= request.max_messages:
                return all_messages
        else:
            logging.debug(f"Skipping folder: {full_path} (not selected)")
        
        # Process sub-folders
        try:
            num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
            for i in range(num_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    if sub_folder:
                        sub_messages = analyze_folder_recursive_with_selection(
                            sub_folder, 
                            request, 
                            full_path, 
                            processed_folders
                        )
                        all_messages.extend(sub_messages)
                        
                        # Stop if we've reached the message limit
                        if request.max_messages and len(all_messages) >= request.max_messages:
                            break
                except Exception as e:
                    logging.warning(f"Error analyzing sub-folder {i} in {full_path}: {str(e)}")
                    continue
        except Exception as e:
            logging.error(f"Error iterating sub-folders in {full_path}: {str(e)}")
    
    except Exception as e:
        logging.error(f"Error in recursive analysis of {current_path}: {str(e)}")
    
    return all_messages


@router.post("/search")
async def search_pst_file(
    request: PSTSearchRequest,
    user: UserModel = Depends(get_verified_user)
):
    """
    Search within PST file for specific content
    """
    check_pypff_available()
    
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="PST file not found")
    
    try:
        pst_file = pypff.file()
        pst_file.open(request.file_path)
        
        root_folder = pst_file.get_root_folder()
        
        if request.selected_folders:
            logging.info(f"Searching in selected folders: {request.selected_folders}")
            search_results = search_folder_recursive_with_selection(root_folder, request)
        else:
            # Fall back to old method for backward compatibility
            search_results = search_folder_recursive(root_folder, request)
        
        pst_file.close()
        
        return JSONResponse(content={
            "query": request.query,
            "search_criteria": request.search_in,
            "results_count": len(search_results),
            "results": search_results
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching PST file: {str(e)}")


def search_folder_recursive(folder, request: PSTSearchRequest) -> List[Dict[str, Any]]:
    """
    Recursively search through folders
    """
    results = []
    query_lower = request.query.lower()
    
    try:
        # Check if folder path matches filter
        folder_path = getattr(folder, 'name', '') or "Unknown"
        if request.folder_path and request.folder_path.lower() not in folder_path.lower():
            # Still search sub-folders
            try:
                num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
                for i in range(num_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        sub_results = search_folder_recursive(sub_folder, request)
                        results.extend(sub_results)
                    except Exception as e:
                        logging.warning(f"Error searching sub-folder {i}: {str(e)}")
                        continue
            except Exception as e:
                logging.error(f"Error iterating sub-folders: {str(e)}")
            return results
        
        # Search messages in current folder
        try:
            num_messages = getattr(folder, 'number_of_sub_messages', 0)
            for i in range(num_messages):
                try:
                    message = folder.get_sub_message(i)
                    
                    # Check date filter
                    sent_time = getattr(message, 'creation_time', None)
                    if request.date_from and sent_time:
                        try:
                            from datetime import datetime
                            date_from = datetime.fromisoformat(request.date_from.replace('Z', '+00:00'))
                            if sent_time < date_from:
                                continue
                        except:
                            pass
                    if request.date_to and sent_time:
                        try:
                            from datetime import datetime
                            date_to = datetime.fromisoformat(request.date_to.replace('Z', '+00:00'))
                            if sent_time > date_to:
                                continue
                        except:
                            pass
                    
                    # Check search criteria
                    match_found = False
                    match_details = []
                    
                    if "subject" in request.search_in:
                        subject = safe_bytes_to_string(getattr(message, 'subject', '')) or ""
                        if safe_search_match(subject, request.query):
                            match_found = True
                            match_details.append(f"Subject: {subject}")
                    
                    if "sender" in request.search_in:
                        sender = safe_bytes_to_string(getattr(message, 'sender_name', '')) or ""
                        if safe_search_match(sender, request.query):
                            match_found = True
                            match_details.append(f"Sender: {sender}")
                    
                    if "body" in request.search_in:
                        try:
                            body = safe_bytes_to_string(getattr(message, 'plain_text_body', '')) or ""
                            if safe_search_match(body, request.query):
                                match_found = True
                                match_details.append("Body content")
                        except Exception as e:
                            logging.warning(f"Error reading message body for search: {str(e)}")
                    
                    if "recipients" in request.search_in:
                        try:
                            num_recipients = getattr(message, 'number_of_recipients', 0)
                            for j in range(num_recipients):
                                try:
                                    recipient = message.get_recipient(j)
                                    email = safe_bytes_to_string(getattr(recipient, 'email_address', '')) or ""
                                    name = safe_bytes_to_string(getattr(recipient, 'name', '')) or ""
                                    if safe_search_match(email, request.query) or safe_search_match(name, request.query):
                                        match_found = True
                                        match_details.append(f"Recipient: {name} <{email}>")
                                except Exception as e:
                                    logging.warning(f"Error reading recipient {j} for search: {str(e)}")
                                    continue
                        except Exception as e:
                            logging.warning(f"Error reading recipients for search: {str(e)}")
                    
                    if match_found:
                        # Safely extract attachment information
                        has_attachments, _ = safe_extract_attachments(message)
                        
                        result = {
                            "subject": safe_bytes_to_string(getattr(message, 'subject', None)),
                            "sender": safe_bytes_to_string(getattr(message, 'sender_name', None)),
                            "sent_time": safe_datetime_to_string(sent_time),
                            "folder_path": folder_path,
                            "match_details": match_details,
                            "has_attachments": has_attachments
                        }
                        results.append(result)
                        
                except Exception as e:
                    logging.warning(f"Error searching message {i}: {str(e)}")
                    continue
        except Exception as e:
            logging.error(f"Error iterating messages: {str(e)}")
        
        # Search sub-folders
        try:
            num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
            for i in range(num_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    sub_results = search_folder_recursive(sub_folder, request)
                    results.extend(sub_results)
                except Exception as e:
                    logging.warning(f"Error searching sub-folder {i}: {str(e)}")
                    continue
        except Exception as e:
            logging.error(f"Error iterating sub-folders: {str(e)}")
    
    except Exception as e:
        logging.error(f"Error in search recursive: {str(e)}")
    
    return results


def search_folder_recursive_with_selection(folder, request: PSTSearchRequest, current_path="") -> List[Dict[str, Any]]:
    """
    Recursively search through folders based on selection criteria
    
    Args:
        folder: pypff folder object
        request: PSTSearchRequest object with selection criteria
        current_path: Current folder path for tracking
        
    Returns:
        List of search result dictionaries
    """
    results = []
    
    try:
        # Get folder name and build current path
        folder_name = safe_bytes_to_string(getattr(folder, 'name', '')) or "Unknown"
        if current_path:
            full_path = f"{current_path}/{folder_name}"
        else:
            full_path = folder_name
        
        # Check if this folder should be searched
        if should_analyze_folder(folder, full_path, request):
            logging.debug(f"Searching in selected folder: {full_path}")
            
            # Search messages in current folder
            try:
                num_messages = getattr(folder, 'number_of_sub_messages', 0)
                for i in range(num_messages):
                    try:
                        message = folder.get_sub_message(i)
                        
                        # Check date filter
                        sent_time = getattr(message, 'creation_time', None)
                        if request.date_from and sent_time:
                            try:
                                from datetime import datetime
                                date_from = datetime.fromisoformat(request.date_from.replace('Z', '+00:00'))
                                if sent_time < date_from:
                                    continue
                            except:
                                pass
                        if request.date_to and sent_time:
                            try:
                                from datetime import datetime
                                date_to = datetime.fromisoformat(request.date_to.replace('Z', '+00:00'))
                                if sent_time > date_to:
                                    continue
                            except:
                                pass
                        
                        # Check search criteria
                        match_found = False
                        match_details = []
                        
                        if "subject" in request.search_in:
                            subject = safe_bytes_to_string(getattr(message, 'subject', '')) or ""
                            if safe_search_match(subject, request.query):
                                match_found = True
                                match_details.append(f"Subject: {subject}")
                        
                        if "sender" in request.search_in:
                            sender = safe_bytes_to_string(getattr(message, 'sender_name', '')) or ""
                            if safe_search_match(sender, request.query):
                                match_found = True
                                match_details.append(f"Sender: {sender}")
                        
                        if "body" in request.search_in:
                            try:
                                body = safe_bytes_to_string(getattr(message, 'plain_text_body', '')) or ""
                                if safe_search_match(body, request.query):
                                    match_found = True
                                    match_details.append("Body content")
                            except Exception as e:
                                logging.warning(f"Error reading message body for search: {str(e)}")
                        
                        if "recipients" in request.search_in:
                            try:
                                num_recipients = getattr(message, 'number_of_recipients', 0)
                                for j in range(num_recipients):
                                    try:
                                        recipient = message.get_recipient(j)
                                        email = safe_bytes_to_string(getattr(recipient, 'email_address', '')) or ""
                                        name = safe_bytes_to_string(getattr(recipient, 'name', '')) or ""
                                        if safe_search_match(email, request.query) or safe_search_match(name, request.query):
                                            match_found = True
                                            match_details.append(f"Recipient: {name} <{email}>")
                                    except Exception as e:
                                        logging.warning(f"Error reading recipient {j} for search: {str(e)}")
                                        continue
                            except Exception as e:
                                logging.warning(f"Error reading recipients for search: {str(e)}")
                        
                        if match_found:
                            # Safely extract attachment information
                            has_attachments, _ = safe_extract_attachments(message)
                            
                            result = {
                                "subject": safe_bytes_to_string(getattr(message, 'subject', None)),
                                "sender": safe_bytes_to_string(getattr(message, 'sender_name', None)),
                                "sent_time": safe_datetime_to_string(sent_time),
                                "folder_path": full_path,
                                "match_details": match_details,
                                "has_attachments": has_attachments
                            }
                            results.append(result)
                            
                    except Exception as e:
                        logging.warning(f"Error searching message {i} in {full_path}: {str(e)}")
                        continue
            except Exception as e:
                logging.error(f"Error iterating messages in {full_path}: {str(e)}")
        else:
            logging.debug(f"Skipping search in folder: {full_path} (not selected)")
        
        # Search sub-folders
        try:
            num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
            for i in range(num_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    if sub_folder:
                        sub_results = search_folder_recursive_with_selection(sub_folder, request, full_path)
                        results.extend(sub_results)
                except Exception as e:
                    logging.warning(f"Error searching sub-folder {i} in {full_path}: {str(e)}")
                    continue
        except Exception as e:
            logging.error(f"Error iterating sub-folders for search in {full_path}: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error in search recursive: {str(e)}")
    
    return results


@router.delete("/cleanup/{file_path}")
async def cleanup_temp_file(
    file_path: str,
    user: UserModel = Depends(get_verified_user)
):
    """
    Clean up temporary PST file
    """
    try:
        if os.path.exists(file_path) and "tmp" in file_path:  # Safety check
            os.unlink(file_path)
            return JSONResponse(content={"message": "File cleaned up successfully"})
        else:
            raise HTTPException(status_code=404, detail="File not found or not a temporary file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up file: {str(e)}")


@router.get("/requirements")
async def get_requirements(user: UserModel = Depends(get_verified_user)):
    """
    Get PST parser requirements and installation status
    """
    requirements = {
        "pypff": {
            "installed": pypff is not None,
            "description": "Python library for PST file parsing",
            "install_command": "pip install libpff-python"
        }
    }
    
    return JSONResponse(content={
        "requirements": requirements,
        "all_satisfied": all(req["installed"] for req in requirements.values())
    })


@router.post("/debug")
async def debug_pst_file(
    request: PSTAnalysisRequest,
    user: UserModel = Depends(get_verified_user)
):
    """
    Debug PST file structure for troubleshooting
    """
    check_pypff_available()
    
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="PST file not found")
    
    try:
        pst_file = pypff.file()
        pst_file.open(request.file_path)
        
        debug_info = {
            "file_info": {
                "path": request.file_path,
                "size": os.path.getsize(request.file_path)
            },
            "root_folder_info": {},
            "pypff_version": getattr(pypff, '__version__', 'unknown'),
            "available_methods": []
        }
        
        # Get root folder
        root_folder = pst_file.get_root_folder()
        if root_folder:
            # Debug root folder properties
            debug_info["root_folder_info"] = {
                "name": getattr(root_folder, 'name', 'No name attribute'),
                "has_name_property": hasattr(root_folder, 'name'),
                "has_number_of_sub_folders": hasattr(root_folder, 'number_of_sub_folders'),
                "has_number_of_sub_messages": hasattr(root_folder, 'number_of_sub_messages'),
                "has_get_sub_folder": hasattr(root_folder, 'get_sub_folder'),
                "has_get_sub_message": hasattr(root_folder, 'get_sub_message'),
                "has_sub_folders_attr": hasattr(root_folder, 'sub_folders'),
                "has_sub_messages_attr": hasattr(root_folder, 'sub_messages'),
            }
            
            # Try to get counts
            try:
                debug_info["root_folder_info"]["sub_folders_count"] = getattr(root_folder, 'number_of_sub_folders', 'N/A')
            except:
                debug_info["root_folder_info"]["sub_folders_count"] = "Error getting count"
                
            try:
                debug_info["root_folder_info"]["sub_messages_count"] = getattr(root_folder, 'number_of_sub_messages', 'N/A')
            except:
                debug_info["root_folder_info"]["sub_messages_count"] = "Error getting count"
            
            # List all available methods and properties
            debug_info["available_methods"] = [attr for attr in dir(root_folder) if not attr.startswith('_')]
        
        pst_file.close()
        
        return JSONResponse(content=debug_info)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error debugging PST file: {str(e)}")


@router.post("/debug/folders")
async def debug_folder_structure(
    request: PSTAnalysisRequest,
    user: UserModel = Depends(get_verified_user)
):
    """
    Debug folder structure for troubleshooting folder loading issues
    """
    check_pypff_available()
    
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="PST file not found")
    
    try:
        pst_file = pypff.file()
        pst_file.open(request.file_path)
        
        root_folder = pst_file.get_root_folder()
        
        def debug_folder_recursive(folder, depth=0, max_depth=5) -> Dict[str, Any]:
            """Recursively debug folder structure with depth limit"""
            if depth > max_depth:
                return {"error": "Max depth reached", "depth": depth}
                
            try:
                folder_name = safe_bytes_to_string(getattr(folder, 'name', None)) or f"Unnamed_Folder_{depth}"
                num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
                num_sub_messages = getattr(folder, 'number_of_sub_messages', 0)
                
                folder_debug = {
                    "name": folder_name,
                    "depth": depth,
                    "num_sub_folders": num_sub_folders,
                    "num_sub_messages": num_sub_messages,
                    "folder_type": get_folder_type(folder),
                    "has_get_sub_folder": hasattr(folder, 'get_sub_folder'),
                    "has_get_sub_message": hasattr(folder, 'get_sub_message'),
                    "sub_folders": [],
                    "errors": []
                }
                
                # Try to access sub-folders
                for i in range(num_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        if sub_folder:
                            sub_debug = debug_folder_recursive(sub_folder, depth + 1, max_depth)
                            folder_debug["sub_folders"].append(sub_debug)
                        else:
                            folder_debug["errors"].append(f"Sub-folder {i} returned None")
                    except Exception as e:
                        folder_debug["errors"].append(f"Error accessing sub-folder {i}: {str(e)}")
                
                return folder_debug
                
            except Exception as e:
                return {
                    "error": str(e),
                    "depth": depth,
                    "folder_accessible": False
                }
        
        debug_info = {
            "file_path": request.file_path,
            "file_size": os.path.getsize(request.file_path),
            "root_folder_debug": debug_folder_recursive(root_folder),
            "total_folders_count": count_folders_recursive(root_folder)
        }
        
        pst_file.close()
        
        return JSONResponse(content=debug_info)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error debugging folder structure: {str(e)}")


def safe_get_message_count(folder) -> int:
    """
    Safely get message count from folder
    
    Args:
        folder: pypff folder object
        
    Returns:
        Number of messages in the folder
    """
    try:
        # Try different ways to get message count
        if hasattr(folder, 'number_of_sub_messages'):
            count = getattr(folder, 'number_of_sub_messages', 0)
            if count is not None and count >= 0:
                return count
        
        # Fallback: try to count messages manually
        if hasattr(folder, 'get_sub_message'):
            try:
                count = 0
                i = 0
                while True:
                    try:
                        message = folder.get_sub_message(i)
                        if message is None:
                            break
                        count += 1
                        i += 1
                        # Safety limit to prevent infinite loops
                        if i > 10000:
                            logging.warning(f"Message count exceeded safety limit of 10000 for folder")
                            break
                    except:
                        break
                return count
            except Exception as e:
                logging.debug(f"Error manually counting messages: {str(e)}")
        
        return 0
        
    except Exception as e:
        logging.warning(f"Error getting message count: {str(e)}")
        return 0


def safe_search_match(text: str, query: str) -> bool:
    """
    Safely check if query matches text with special handling for common cases
    
    Args:
        text: Text to search in
        query: Search query
        
    Returns:
        True if query matches text
    """
    if not text and not query:
        return True
    
    if not text:
        text = ""
    
    if not query:
        return True
    
    text_lower = text.lower().strip()
    query_lower = query.lower().strip()
    
    # Handle special case for "(Geen onderwerp)" which might be represented differently
    if query_lower in ["(geen onderwerp)", "geen onderwerp"]:
        return (
            text_lower in ["", "(geen onderwerp)", "geen onderwerp", "no subject", "(no subject)"] or
            text_lower.startswith("(geen ") or
            text_lower.startswith("(no ")
        )
    
    # Handle parentheses in search - remove them for matching
    if query_lower.startswith("(") and query_lower.endswith(")"):
        query_stripped = query_lower[1:-1]
        if query_stripped in text_lower:
            return True
    
    # Regular substring match
    return query_lower in text_lower


@router.post("/debug/search")
async def debug_search(
    request: PSTSearchRequest,
    user: UserModel = Depends(get_verified_user)
):
    """
    Debug search functionality to understand why searches might fail
    """
    check_pypff_available()
    
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="PST file not found")
    
    try:
        pst_file = pypff.file()
        pst_file.open(request.file_path)
        
        root_folder = pst_file.get_root_folder()
        
        def debug_search_folder(folder, depth=0, max_depth=3) -> Dict[str, Any]:
            """Debug search in a specific folder"""
            if depth > max_depth:
                return {"skipped": "Max depth reached"}
                
            folder_name = safe_bytes_to_string(getattr(folder, 'name', '')) or f"Unknown_{depth}"
            
            folder_debug = {
                "folder_name": folder_name,
                "depth": depth,
                "message_count": safe_get_message_count(folder),
                "messages_analyzed": 0,
                "matches_found": 0,
                "sample_subjects": [],
                "search_errors": []
            }
            
            try:
                num_messages = getattr(folder, 'number_of_sub_messages', 0)
                max_sample = min(10, num_messages)  # Only check first 10 messages for debug
                
                for i in range(max_sample):
                    try:
                        message = folder.get_sub_message(i)
                        folder_debug["messages_analyzed"] += 1
                        
                        # Get subject for analysis
                        subject = safe_bytes_to_string(getattr(message, 'subject', '')) or "(Geen onderwerp)"
                        folder_debug["sample_subjects"].append(subject)
                        
                        # Test search match
                        if "subject" in request.search_in:
                            if safe_search_match(subject, request.query):
                                folder_debug["matches_found"] += 1
                                
                    except Exception as e:
                        folder_debug["search_errors"].append(f"Message {i}: {str(e)}")
                        
            except Exception as e:
                folder_debug["search_errors"].append(f"Folder iteration: {str(e)}")
            
            return folder_debug
        
        debug_info = {
            "search_query": request.query,
            "search_in": request.search_in,
            "file_path": request.file_path,
            "folders_analyzed": []
        }
        
        # Debug specific folders that should have the searched content
        target_folders = ["Concepten", "Verwijderde items", "Ongewenste e-mail"]
        
        def find_and_debug_folder(folder, target_name, current_path="") -> bool:
            """Find and debug a specific folder"""
            folder_name = safe_bytes_to_string(getattr(folder, 'name', '')) or "Unknown"
            
            if target_name.lower() in folder_name.lower():
                debug_result = debug_search_folder(folder)
                debug_result["full_path"] = f"{current_path}/{folder_name}".strip("/")
                debug_info["folders_analyzed"].append(debug_result)
                return True
            
            # Search sub-folders
            try:
                num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
                for i in range(num_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        if find_and_debug_folder(sub_folder, target_name, f"{current_path}/{folder_name}".strip("/")):
                            return True
                    except:
                        continue
            except:
                pass
            
            return False
        
        # Find and debug target folders
        for target in target_folders:
            find_and_debug_folder(root_folder, target)
        
        pst_file.close()
        
        return JSONResponse(content=debug_info)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error debugging search: {str(e)}")


def calculate_total_messages(folder) -> int:
    """
    Recursively calculate total messages in all folders
    
    Args:
        folder: pypff folder object
        
    Returns:
        Total number of messages
    """
    total = 0
    
    try:
        # Count messages in current folder
        total += safe_get_message_count(folder)
        
        # Count messages in sub-folders
        try:
            num_sub_folders = getattr(folder, 'number_of_sub_folders', 0)
            for i in range(num_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    if sub_folder:
                        total += calculate_total_messages(sub_folder)
                except Exception as e:
                    logging.warning(f"Error calculating messages in sub-folder {i}: {str(e)}")
                    continue
        except Exception as e:
            logging.warning(f"Error iterating sub-folders for message count: {str(e)}")
            
    except Exception as e:
        logging.error(f"Error calculating total messages: {str(e)}")
    
    return total


def is_folder_selected(folder_path: str, selected_folders: Optional[List[str]]) -> bool:
    """
    Check if a folder is in the selected folders list
    
    Args:
        folder_path: Path of the folder to check
        selected_folders: List of selected folder paths
        
    Returns:
        True if folder should be processed
    """
    if not selected_folders:
        return True  # If no selection, process all folders
    
    # Normalize paths for comparison
    folder_path_norm = folder_path.strip('/').lower()
    
    for selected in selected_folders:
        selected_norm = selected.strip('/').lower()
        
        # Exact match
        if folder_path_norm == selected_norm:
            return True
            
        # Check if current folder is a subfolder of selected folder
        if folder_path_norm.startswith(selected_norm + '/'):
            return True
            
        # Check if selected folder is a subfolder of current folder (include parent)
        if selected_norm.startswith(folder_path_norm + '/'):
            return True
    
    return False


def should_analyze_folder(folder, current_path: str, request) -> bool:
    """
    Determine if a folder should be analyzed based on filters and selections
    
    Args:
        folder: pypff folder object
        current_path: Current folder path
        request: Analysis or search request object
        
    Returns:
        True if folder should be analyzed
    """
    # Check selected folders filter
    if hasattr(request, 'selected_folders') and request.selected_folders:
        if not is_folder_selected(current_path, request.selected_folders):
            return False
    
    # Check old folder_filter for backward compatibility
    if hasattr(request, 'folder_filter') and request.folder_filter:
        folder_name = safe_bytes_to_string(getattr(folder, 'name', '')) or ""
        if request.folder_filter.lower() not in folder_name.lower():
            return False
    
    return True

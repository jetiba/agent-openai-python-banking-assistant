"""Adaptive Card builders for M365 Agent SDK responses.

This module provides functions to build Adaptive Cards for various scenarios,
including tool approval requests, progress indicators, and rich responses.
"""

from typing import Any, Dict


def build_approval_card(
    tool_name: str,
    tool_args: Dict[str, Any],
    call_id: str,
    request_id: str
) -> Dict[str, Any]:
    """Build an Adaptive Card for tool approval requests.
    
    Args:
        tool_name: Name of the tool requesting approval
        tool_args: Arguments passed to the tool
        call_id: The function call ID
        request_id: The approval request ID
        
    Returns:
        Adaptive Card JSON structure
    """
    # Format the arguments for display
    args_display = []
    for key, value in tool_args.items():
        args_display.append({
            "type": "TextBlock",
            "text": f"**{key}:** {value}",
            "wrap": True,
            "size": "Small"
        })
    
    # Get human-friendly tool description
    tool_descriptions = {
        "processPayment": "Process Payment",
        "transferFunds": "Transfer Funds",
        "updateAccount": "Update Account",
        "deleteTransaction": "Delete Transaction",
    }
    display_name = tool_descriptions.get(tool_name, tool_name)
    
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "Container",
                "style": "warning",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "⚠️ Action Requires Approval",
                        "weight": "Bolder",
                        "size": "Medium"
                    }
                ]
            },
            {
                "type": "TextBlock",
                "text": f"The assistant wants to execute: **{display_name}**",
                "wrap": True,
                "spacing": "Medium"
            },
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Details:",
                        "weight": "Bolder",
                        "size": "Small"
                    },
                    *args_display
                ],
                "spacing": "Small"
            },
            {
                "type": "TextBlock",
                "text": "Do you want to proceed with this action?",
                "wrap": True,
                "spacing": "Medium"
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "✓ Approve",
                "style": "positive",
                "data": {
                    "action": "approval",
                    "approved": True,
                    "call_id": call_id,
                    "request_id": request_id,
                    "tool_name": tool_name
                }
            },
            {
                "type": "Action.Submit",
                "title": "✗ Reject",
                "style": "destructive",
                "data": {
                    "action": "approval",
                    "approved": False,
                    "call_id": call_id,
                    "request_id": request_id,
                    "tool_name": tool_name
                }
            }
        ]
    }
    
    return card


def build_progress_card(title: str, status: str = "in_progress") -> Dict[str, Any]:
    """Build an Adaptive Card showing progress/status.
    
    Args:
        title: The progress message to display
        status: Status type - "in_progress", "completed", "error"
        
    Returns:
        Adaptive Card JSON structure
    """
    icons = {
        "in_progress": "🔄",
        "completed": "✅",
        "error": "❌"
    }
    icon = icons.get(status, "🔄")
    
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"{icon} {title}",
                "wrap": True
            }
        ]
    }
    
    return card


def build_welcome_card() -> Dict[str, Any]:
    """Build a welcome Adaptive Card for new conversations.
    
    Returns:
        Adaptive Card JSON structure
    """
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "👋 Welcome to Banking Assistant",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": "I can help you with:",
                "wrap": True,
                "spacing": "Medium"
            },
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "• **Account Information** - Check balances, view account details",
                        "wrap": True
                    },
                    {
                        "type": "TextBlock",
                        "text": "• **Transaction History** - View recent transactions, search by recipient",
                        "wrap": True
                    },
                    {
                        "type": "TextBlock",
                        "text": "• **Payments** - Make payments, upload invoices for processing",
                        "wrap": True
                    }
                ]
            },
            {
                "type": "TextBlock",
                "text": "How can I help you today?",
                "wrap": True,
                "spacing": "Medium",
                "weight": "Bolder"
            }
        ]
    }
    
    return card


def build_error_card(message: str, allow_retry: bool = True) -> Dict[str, Any]:
    """Build an Adaptive Card for error messages.
    
    Args:
        message: The error message to display
        allow_retry: Whether to show a retry suggestion
        
    Returns:
        Adaptive Card JSON structure
    """
    body = [
        {
            "type": "Container",
            "style": "attention",
            "items": [
                {
                    "type": "TextBlock",
                    "text": "❌ Error",
                    "weight": "Bolder",
                    "color": "Attention"
                },
                {
                    "type": "TextBlock",
                    "text": message,
                    "wrap": True
                }
            ]
        }
    ]
    
    if allow_retry:
        body.append({
            "type": "TextBlock",
            "text": "Please try again or rephrase your request.",
            "wrap": True,
            "spacing": "Medium",
            "isSubtle": True
        })
    
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body
    }
    
    return card

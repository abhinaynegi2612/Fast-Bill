"""
Command Processor - Module 2: Intelligent Bill Reader
Processes natural language commands on bill data
"""
import re
import pandas as pd
from typing import Dict, Any, Optional, Callable
from collections import Counter
import logging

from app.models.schemas import BillData, CommandType, CommandResponse
from app.services.bill_parser import bill_parser

logger = logging.getLogger(__name__)


class CommandProcessor:
    """
    Rule-based + Optional LLM command processor
    Maps user queries to bill data operations
    """
    
    # Intent patterns for rule-based matching
    INTENT_PATTERNS = {
        CommandType.TOTAL: [
            r'total\s*(?:amount|bill|price)?',
            r'grand\s*total',
            r'how\s*much\s*did\s*i\s*(?:pay|spend)',
            r'final\s*amount',
        ],
        CommandType.GST: [
            r'gst\s*(?:amount|tax|value)?',
            r'tax\s*(?:amount|value)?',
            r'how\s*much\s*(?:is\s*)?gst',
            r'how\s*much\s*tax',
        ],
        CommandType.SMALLEST_AMOUNT: [
            r'smallest\s*(?:amount|price|item)',
            r'cheapest\s*(?:item|price)',
            r'least\s*(?:amount|price)',
            r'minimum\s*(?:price|amount)',
        ],
        CommandType.LARGEST_AMOUNT: [
            r'largest\s*(?:amount|price)',
            r'most\s*expensive\s*item',
            r'highest\s*(?:amount|price)',
            r'maximum\s*(?:price|amount)',
            r'most\s*expensive',  # Added
            r'expensive',  # Added
        ],
        CommandType.MOST_EXPENSIVE_ITEM: [
            r'most\s*expensive\s*item',
            r'costliest\s*item',
            r'highest\s*price\s*item',
            r'most\s*expensive',  # Added
            r'expensive',  # Added
        ],
        CommandType.LEAST_EXPENSIVE_ITEM: [
            r'least\s*expensive\s*item',
            r'cheapest\s*item',
            r'lowest\s*price\s*item',
            r'cheapest',  # Added
            r'cheap',  # Added
        ],
        CommandType.HIGHEST_QUANTITY: [
            r'highest\s*quantity',
            r'most\s*quantity',
            r'item\s*with\s*most\s*qty',
            r'which\s*item\s*has\s*most\s*quantity',
        ],
        CommandType.LIST_ITEMS: [
            r'list\s*(?:all\s*)?items',
            r'what\s*did\s*i\s*buy',
            r'items\s*purchased',
            r'show\s*all\s*items',
        ],
        CommandType.ITEM_COUNT: [
            r'how\s*many\s*items',
            r'number\s*of\s*items',
            r'count\s*of\s*items',
            r'total\s*items',
        ],
        CommandType.AVERAGE_PRICE: [
            r'average\s*(?:price|amount)',
            r'mean\s*(?:price|amount)',
        ],
        CommandType.FIND_ITEM: [
            r'(?:find|search|look\s*for)\s*(.+)',
            r'do\s*i\s*have\s*(.+)',
            r'is\s*(.+)\s*in\s*the\s*bill',
        ],
        CommandType.DUPLICATE_ITEMS: [
            r'duplicate\s*items',
            r'items\s*appearing\s*twice',
            r'which\s*items?\s*appear\s*twice',
        ],
        CommandType.SUMMARY: [
            r'summary\s*(?:of\s*bill)?',
            r'bill\s*summary',
            r'overview\s*(?:of\s*bill)?',
            r'give\s*me\s*a\s*summary',
        ],
    }
    
    def __init__(self):
        self.bill_data: Optional[BillData] = None
        self.df: Optional[pd.DataFrame] = None
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Map intents to handler functions"""
        self.handlers: Dict[CommandType, Callable[[], Dict[str, Any]]] = {
            CommandType.TOTAL: self._handle_total,
            CommandType.GST: self._handle_gst,
            CommandType.SMALLEST_AMOUNT: self._handle_smallest_amount,
            CommandType.LARGEST_AMOUNT: self._handle_largest_amount,
            CommandType.MOST_EXPENSIVE_ITEM: self._handle_most_expensive,
            CommandType.LEAST_EXPENSIVE_ITEM: self._handle_least_expensive,
            CommandType.HIGHEST_QUANTITY: self._handle_highest_quantity,
            CommandType.LIST_ITEMS: self._handle_list_items,
            CommandType.ITEM_COUNT: self._handle_item_count,
            CommandType.AVERAGE_PRICE: self._handle_average_price,
            CommandType.FIND_ITEM: self._handle_find_item,
            CommandType.DUPLICATE_ITEMS: self._handle_duplicates,
            CommandType.SUMMARY: self._handle_summary,
        }
    
    def load_bill(self, bill_data: BillData):
        """Load bill data for processing"""
        self.bill_data = bill_data
        if bill_data.items:
            self.df = pd.DataFrame([
                {
                    'name': item.name,
                    'quantity': item.quantity,
                    'unit': item.unit,
                    'price': item.price,
                    'amount': item.amount
                }
                for item in bill_data.items
            ])
        else:
            self.df = None
    
    def process_command(self, command: str) -> CommandResponse:
        """
        Main entry point: Process user command
        """
        import time
        start_time = time.time()
        
        if not self.bill_data:
            return CommandResponse(
                command=command,
                intent="error",
                answer="No bill data loaded. Please upload a bill first.",
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        
        # Detect intent
        intent, confidence, params = self._detect_intent(command.lower())
        
        # Execute handler
        if intent in self.handlers:
            try:
                result = self.handlers[intent]()
                answer = self._format_answer(intent, result, params)
                
                return CommandResponse(
                    command=command,
                    intent=intent.value,
                    answer=answer,
                    data=result,
                    bill_summary=self.bill_data if intent == CommandType.SUMMARY else None,
                    confidence=confidence,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            except Exception as e:
                logger.error(f"Error executing handler for {intent}: {e}")
                return CommandResponse(
                    command=command,
                    intent=intent.value,
                    answer=f"Sorry, I couldn't process that query. Error: {str(e)}",
                    confidence=confidence,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
        else:
            return CommandResponse(
                command=command,
                intent="unknown",
                answer="I'm not sure how to answer that. Try asking about: total amount, GST, items, prices, or a summary.",
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _detect_intent(self, command: str) -> tuple[CommandType, float, Dict[str, Any]]:
        """Detect intent using pattern matching"""
        params = {}
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, command, re.IGNORECASE)
                if match:
                    # Check for item name in find_item pattern
                    if intent == CommandType.FIND_ITEM and len(match.groups()) > 0:
                        params['item_name'] = match.group(1).strip()
                    return intent, 0.9, params
        
        # Default: Try to extract any item name mentioned
        return CommandType.SUMMARY, 0.5, params  # Changed from CUSTOM to SUMMARY
    
    def _format_answer(self, intent: CommandType, result: Dict[str, Any], params: Dict[str, Any]) -> str:
        """Format the answer based on intent and result"""
        currency = self.bill_data.currency if self.bill_data else "₹"
        
        formatters = {
            CommandType.TOTAL: lambda: f"Total Amount: {currency}{result.get('total', 0):.2f}",
            CommandType.GST: lambda: f"GST Amount: {currency}{result.get('gst', 0):.2f}",
            CommandType.SMALLEST_AMOUNT: lambda: f"Smallest amount: {currency}{result.get('amount', 0):.2f}",
            CommandType.LARGEST_AMOUNT: lambda: f"Largest amount: {currency}{result.get('amount', 0):.2f}",
            CommandType.MOST_EXPENSIVE_ITEM: lambda: f"Most expensive item: {result.get('item_name', 'Unknown')} – {currency}{result.get('amount', 0):.2f}",
            CommandType.LEAST_EXPENSIVE_ITEM: lambda: f"Least expensive item: {result.get('item_name', 'Unknown')} – {currency}{result.get('amount', 0):.2f}",
            CommandType.HIGHEST_QUANTITY: lambda: f"Item with highest quantity: {result.get('item_name', 'Unknown')} ({result.get('quantity', 0)} {result.get('unit', 'pcs')})",
            CommandType.LIST_ITEMS: lambda: self._format_item_list(result.get('items', [])),
            CommandType.ITEM_COUNT: lambda: f"Total items: {result.get('count', 0)}",
            CommandType.AVERAGE_PRICE: lambda: f"Average item price: {currency}{result.get('average', 0):.2f}",
            CommandType.FIND_ITEM: lambda: result.get('message', 'Item not found'),
            CommandType.DUPLICATE_ITEMS: lambda: result.get('message', 'No duplicates found'),
            CommandType.SUMMARY: lambda: self._format_summary(result),
        }
        
        return formatters.get(intent, lambda: str(result))()
    
    # ===== HANDLER METHODS =====
    
    def _handle_total(self) -> Dict[str, Any]:
        return {'total': self.bill_data.total_amount}
    
    def _handle_gst(self) -> Dict[str, Any]:
        return {
            'gst': self.bill_data.gst_amount,
            'gst_rate': self.bill_data.gst_rate,
            'subtotal': self.bill_data.subtotal
        }
    
    def _handle_smallest_amount(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'amount': 0, 'item_name': 'N/A'}
        min_row = self.df.loc[self.df['amount'].idxmin()]
        return {
            'amount': float(min_row['amount']),
            'item_name': str(min_row['name']),
            'quantity': float(min_row['quantity'])
        }
    
    def _handle_largest_amount(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'amount': 0, 'item_name': 'N/A'}
        max_row = self.df.loc[self.df['amount'].idxmax()]
        return {
            'amount': float(max_row['amount']),
            'item_name': str(max_row['name']),
            'quantity': float(max_row['quantity'])
        }
    
    def _handle_most_expensive(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'item_name': 'N/A', 'amount': 0}
        max_row = self.df.loc[self.df['amount'].idxmax()]
        return {
            'item_name': str(max_row['name']),
            'amount': float(max_row['amount']),
            'price': float(max_row['price']),
            'quantity': float(max_row['quantity'])
        }
    
    def _handle_least_expensive(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'item_name': 'N/A', 'amount': 0}
        min_row = self.df.loc[self.df['amount'].idxmin()]
        return {
            'item_name': str(min_row['name']),
            'amount': float(min_row['amount']),
            'price': float(min_row['price']),
            'quantity': float(min_row['quantity'])
        }
    
    def _handle_highest_quantity(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'item_name': 'N/A', 'quantity': 0}
        max_row = self.df.loc[self.df['quantity'].idxmax()]
        return {
            'item_name': str(max_row['name']),
            'quantity': float(max_row['quantity']),
            'unit': str(max_row['unit']),
            'amount': float(max_row['amount'])
        }
    
    def _handle_list_items(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'items': [], 'count': 0}
        items = self.df.to_dict('records')
        return {'items': items, 'count': len(items)}
    
    def _handle_item_count(self) -> Dict[str, Any]:
        count = len(self.bill_data.items) if self.bill_data.items else 0
        return {'count': count}
    
    def _handle_average_price(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'average': 0, 'count': 0}
        avg = self.df['amount'].mean()
        return {'average': float(avg), 'count': len(self.df)}
    
    def _handle_find_item(self) -> Dict[str, Any]:
        # This would need params passed from detect_intent
        # For now, search all items
        if self.df is None or self.df.empty:
            return {'found': False, 'message': 'No items to search'}
        
        # Return all items for now (would filter by params)
        items = self.df.to_dict('records')
        return {
            'found': True,
            'items': items,
            'message': f"Found {len(items)} items in the bill"
        }
    
    def _handle_duplicates(self) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
            return {'duplicates': [], 'message': 'No items to check'}
        
        name_counts = Counter(self.df['name'].str.lower())
        duplicates = [name for name, count in name_counts.items() if count > 1]
        
        if duplicates:
            return {
                'duplicates': duplicates,
                'message': f"Items appearing multiple times: {', '.join(duplicates)}"
            }
        return {'duplicates': [], 'message': 'No duplicate items found'}
    
    def _handle_summary(self) -> Dict[str, Any]:
        if self.df is None:
            item_count = 0
        else:
            item_count = len(self.df)
        
        return {
            'vendor': self.bill_data.vendor_name,
            'bill_number': self.bill_data.bill_number,
            'bill_date': self.bill_data.bill_date,
            'item_count': item_count,
            'subtotal': self.bill_data.subtotal,
            'gst': self.bill_data.gst_amount,
            'gst_rate': self.bill_data.gst_rate,
            'total': self.bill_data.total_amount,
            'currency': self.bill_data.currency
        }
    
    # ===== FORMATTERS =====
    
    def _format_item_list(self, items: list) -> str:
        if not items:
            return "No items found in the bill."
        
        lines = ["Items in your bill:"]
        for i, item in enumerate(items, 1):
            name = item.get('name', 'Unknown')
            qty = item.get('quantity', 0)
            unit = item.get('unit', 'pcs')
            amount = item.get('amount', 0)
            lines.append(f"{i}. {name} – {qty} {unit} – ₹{amount:.2f}")
        
        return "\n".join(lines)
    
    def _format_summary(self, result: Dict[str, Any]) -> str:
        currency = result.get('currency', '₹')
        lines = [
            f"Bill Summary:",
            f"- Vendor: {result.get('vendor', 'Unknown')}",
            f"- Bill #: {result.get('bill_number', 'N/A')}",
            f"- Date: {result.get('bill_date', 'N/A')}",
            f"- Items: {result.get('item_count', 0)}",
            f"- Subtotal: {currency}{result.get('subtotal', 0):.2f}",
            f"- GST ({result.get('gst_rate', 0)}%): {currency}{result.get('gst', 0):.2f}",
            f"- Total: {currency}{result.get('total', 0):.2f}"
        ]
        return "\n".join(lines)


# Singleton instance
command_processor = CommandProcessor()

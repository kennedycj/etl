"""Classify transactions for double-entry ledger.

Determines if a transaction is:
- External (expense/income) -> account <-> Expenses:Category or Income:Source
- Internal transfer -> account <-> account
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import re


def extract_transfer_accounts(original_description: str, account_name: str, 
                              category: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """Extract source and target accounts from transfer transaction.
    
    Args:
        original_description: Original description (contains source account info)
        account_name: Account Name column (target account)
        category: Transaction category (if "Transfers", definitely a transfer)
        
    Returns:
        Tuple of (source_account_description, target_account_name) if transfer, None otherwise
    """
    # Check if category indicates transfer
    if category and category.lower() in ['transfers', 'transfer']:
        # Extract source account from original description
        # Format: "Online scheduled transfer from CHK 0129" or similar
        desc_lower = original_description.lower()
        
        # Common patterns
        if 'from' in desc_lower:
            # "transfer from CHK 0129" - account_name is the TARGET (where money goes)
            parts = desc_lower.split('from', 1)  # Split on first 'from' only
            if len(parts) > 1:
                source_info = parts[1].strip()
                # Clean up source info (remove confirmation numbers, etc.)
                # "chk 0129 confirmation# xxxxxx3987" -> "chk 0129"
                source_info = source_info.split('confirmation')[0].strip()
                source_info = source_info.split('conf#')[0].strip()
                return (source_info, account_name)
        elif 'to' in desc_lower:
            # "transfer to SAV 1234" - account_name is the SOURCE (where money comes from)
            parts = desc_lower.split('to', 1)  # Split on first 'to' only
            if len(parts) > 1:
                target_info = parts[1].strip()
                # Clean up target info
                target_info = target_info.split('confirmation')[0].strip()
                target_info = target_info.split('conf#')[0].strip()
                return (account_name, target_info)  # account_name is source, target_info is target
    
    return None


def map_account_identifier_to_name(account_identifier: str, institution: str) -> Optional[str]:
    """Map account identifier (e.g., "CHK 0129", "SAV 5990") to full account name.
    
    Args:
        account_identifier: Account identifier from description (e.g., "CHK 0129", "SAV 5990")
        institution: Institution name
        
    Returns:
        Mapped account name or None
    """
    identifier_lower = account_identifier.lower().strip()
    
    # Map account type abbreviations
    account_type_map = {
        'chk': 'Checking',
        'checking': 'Checking',
        'sav': 'Savings',
        'savings': 'Savings',
        'cd': 'CD',
        'credit': 'Credit Card',
        'cc': 'Credit Card'
    }
    
    # Check for account type abbreviation
    for abbrev, account_type in account_type_map.items():
        if abbrev in identifier_lower:
            # For Bank of America, construct the account name
            # "CHK 0129" -> "Bank of America - Bank - Checking"
            # "SAV 5990" -> "Bank of America - Bank - Savings" or "Bank of America - Bank - Regular Savings"
            if account_type == 'Savings':
                # Try to match specific savings account names
                # Could be "Regular Savings" or just "Savings"
                return f"{institution} - Bank - Regular Savings"
            else:
                return f"{institution} - Bank - {account_type}"
    
    return None


def classify_transaction_type(description: str, amount: Decimal, 
                             account_type: str, category: Optional[str] = None,
                             original_description: Optional[str] = None) -> str:
    """Classify transaction type for ledger posting.
    
    Args:
        description: Transaction description
        amount: Transaction amount
        account_type: Type of account (checking, savings, credit_card, etc.)
        category: Transaction category from CSV
        original_description: Original description (may contain transfer info)
        
    Returns:
        Transaction type: 'expense', 'income', 'transfer', 'credit_card_payment', 'investment_contribution', 'liability_payment', 'unknown'
    """
    # Check for "Bill Payment" in description FIRST - it's always an expense, not a credit card payment
    # This must come before category checks to override any category misclassification
    description_lower_precheck = description.lower()
    orig_desc_lower_precheck = (original_description or '').lower()
    if 'bill payment' in description_lower_precheck or 'bill payment' in orig_desc_lower_precheck:
        return 'expense'  # Bill payments are always expenses, regardless of category
    
    # Check category - most reliable indicator (but bill payment check above takes precedence)
    if category:
        cat_lower = category.lower()
        if cat_lower in ['transfers', 'transfer']:
            return 'transfer'
        elif cat_lower in ['credit card payments', 'credit card payment', 'credit cards']:
            return 'credit_card_payment'
        # Note: "Bill Payment" is NOT a credit card payment - it's an expense
        # Check for bill payment in description BEFORE checking other categories
        desc_lower_check = description.lower()
        if 'bill payment' in desc_lower_check:
            return 'expense'  # Bill payments are expenses, not credit card payments
        elif cat_lower in ['mortgages', 'mortgage']:
            return 'liability_payment'  # Mortgage payment reduces liability
        elif cat_lower in ['loans', 'loan', 'student loan', 'student loans']:
            return 'liability_payment'  # Loan payment reduces liability
        elif cat_lower in ['savings', '529', '529k', 'investment', 'investments']:
            # Investment contributions are asset movements, not expenses
            return 'investment_contribution'
        # Other categories are likely expenses
    
    description_lower = description.lower()
    orig_desc_lower = (original_description or '').lower()
    
    # Check for bill payment FIRST - it's an expense, not a credit card payment
    # This must come before category checks to override any category misclassification
    if 'bill payment' in description_lower or 'bill payment' in orig_desc_lower:
        return 'expense'
    
    # Investment contribution indicators (529, IRA, 401k, etc.)
    investment_keywords = ['529', 'ira', '401k', '401(k)', 'contribution', 'contrib', 
                          'mn dir', 'mn dir ach', 'direct ach', 'investment contribution']
    
    # Check for investment contributions in description
    if any(keyword in description_lower or keyword in orig_desc_lower 
           for keyword in investment_keywords):
        return 'investment_contribution'
    
    # Liability payment indicators (student loans, mortgages, auto loans, etc.)
    # Note: "US BANK" is commonly a mortgage servicer
    # "FORD CREDIT" is an auto loan servicer
    liability_keywords = ['student loan', 'student loans', 'mortgage', 'heloc', 
                        'loan payment', 'loan pay', 'us bank', 'ford credit',
                        'auto loan', 'car loan', 'vehicle loan']
    
    # Check for liability payments in description
    if any(keyword in description_lower or keyword in orig_desc_lower 
           for keyword in liability_keywords):
        return 'liability_payment'
    
    # Income indicators
    income_keywords = ['salary', 'payroll', 'deposit', 'interest earned', 'dividend', 
                      'refund', 'reimbursement']
    
    # Transfer indicators
    transfer_keywords = ['transfer', 'online transfer', 'scheduled transfer', 
                        'ach transfer', 'wire transfer']
    
    # Check if it's a transfer from description
    if any(keyword in description_lower or keyword in orig_desc_lower 
           for keyword in transfer_keywords):
        return 'transfer'
    
    # For credit cards, negative amounts are expenses (spending)
    if account_type in ['credit_card'] and amount < 0:
        return 'expense'
    
    # For checking/savings, positive amounts are usually income
    if account_type in ['checking', 'savings'] and amount > 0:
        if any(keyword in description_lower for keyword in income_keywords):
            return 'income'
        # Could be transfer - check description
        if any(keyword in description_lower for keyword in transfer_keywords):
            return 'transfer'
        return 'income'  # Default positive to income
    
    # For checking/savings, negative amounts
    if account_type in ['checking', 'savings'] and amount < 0:
        # Check for transfer indicators first
        if any(keyword in description_lower or keyword in orig_desc_lower 
               for keyword in transfer_keywords):
            return 'transfer'
        # Bill payments are expenses (check this before defaulting)
        # Must check for "bill payment" explicitly to avoid confusion with credit card payments
        if 'bill payment' in description_lower or 'bill payment' in orig_desc_lower:
            return 'expense'
        # Check for credit card payment indicators (more specific than just "payment")
        if ('credit card' in description_lower or 'credit card' in orig_desc_lower or
            (category and 'credit card' in category.lower())):
            return 'credit_card_payment'
        # Default negative to expense
        return 'expense'
    
    return 'unknown'


def create_ledger_postings(account_name: str, amount: Decimal, transaction_type: str,
                          description: str, other_account: Optional[str] = None,
                          category: Optional[str] = None, 
                          source_account_name: Optional[str] = None,
                          target_account_name: Optional[str] = None,
                          institution: str = "Unknown") -> List[Tuple[str, Decimal]]:
    """Create double-entry postings for a transaction.
    
    Args:
        account_name: Primary account name (target for transfers, account for expenses/income)
        amount: Transaction amount (positive = money in, negative = money out)
        transaction_type: 'expense', 'income', 'transfer', 'credit_card_payment', 'unknown'
        description: Transaction description
        other_account: Other account if transfer (legacy parameter)
        category: Expense/income category
        source_account_name: Source account name for transfers
        target_account_name: Target account name for transfers (if different from account_name)
        institution: Institution name for account mapping
        
    Returns:
        List of (account, amount) tuples that balance to zero
    """
    postings = []
    
    # Map account names to ledger accounts
    def get_ledger_account(acc_name, acc_type=None):
        if not acc_type:
            # Infer from account name - be more specific
            acc_name_lower = acc_name.lower()
            if 'savings' in acc_name_lower and 'checking' not in acc_name_lower:
                acc_type = 'savings'
            elif 'checking' in acc_name_lower or ('bank' in acc_name_lower and 'savings' not in acc_name_lower):
                acc_type = 'checking'
            elif 'credit' in acc_name_lower or 'card' in acc_name_lower:
                acc_type = 'credit_card'
            elif 'cd' in acc_name_lower:
                acc_type = 'cd'
            else:
                # Try to infer from institution-specific patterns
                if 'regular savings' in acc_name_lower:
                    acc_type = 'savings'
                elif 'adv plus' in acc_name_lower or 'adv plus banking' in acc_name_lower:
                    acc_type = 'checking'
                else:
                    acc_type = 'checking'  # Default
        return map_account_to_ledger_account(acc_name, acc_type, institution)
    
    if transaction_type == 'transfer' and source_account_name:
        # Internal transfer: source_account -> target_account
        # Use target_account_name if provided, otherwise use account_name
        target_account = target_account_name if target_account_name else account_name
        source_ledger = get_ledger_account(source_account_name)
        target_ledger = get_ledger_account(target_account)
        postings.append((source_ledger, -abs(amount)))  # Negative from source
        postings.append((target_ledger, abs(amount)))  # Positive to target
    
    elif transaction_type == 'investment_contribution':
        # Investment contribution: Assets:Checking -> Assets:Investments:529/IRA/etc.
        # Amount is negative (money going out of checking)
        # Determine investment account type from description or category
        desc_lower = description.lower()
        # Check for 529 indicators first (MN DIR is Minnesota Direct 529)
        # 529 accounts are state-managed, not institution-specific
        if ('529' in desc_lower or 'mn dir' in desc_lower or 
            (category and '529' in category.lower())):
            investment_account = "Assets:Investments:529"
        elif 'ira' in desc_lower or (category and 'ira' in category.lower()):
            # IRA accounts are institution-specific
            # Could be traditional, roth, or rollover - default to traditional
            investment_account = f"Assets:Investments:IRA:Traditional:{institution}"
        elif '401' in desc_lower or '401k' in desc_lower or (category and '401' in category.lower()):
            # 401k accounts are employer/institution-specific
            investment_account = f"Assets:Investments:401k:{institution}"
        else:
            # Default to 529 if category says "savings" (common mistake in categorization)
            # or if description contains "CONTRIB" (likely 529 contribution)
            if (category and 'savings' in category.lower()) or 'contrib' in desc_lower:
                investment_account = "Assets:Investments:529"
            else:
                investment_account = f"Assets:Investments:Other:{institution}"
        
        checking_ledger = get_ledger_account(account_name, 'checking')
        postings.append((checking_ledger, amount))  # Negative from checking
        postings.append((investment_account, -amount))  # Positive to investment (increases asset)
    
    elif transaction_type == 'liability_payment':
        # Liability payment: Assets:Checking -> Liabilities:StudentLoans/Mortgage/etc.
        # Amount is negative (money going out of checking)
        # Determine liability type from description or category
        desc_lower = description.lower()
        cat_lower = (category or '').lower()
        
        # Check category first (most reliable) - handle both "Mortgage" and "Mortgages"
        # Mortgages are serviced by different institutions, so don't include payment source institution
        if 'mortgage' in cat_lower or 'mortgages' in cat_lower:
            liability_account = "Liabilities:Mortgage"
        elif 'student loan' in cat_lower:
            liability_account = "Liabilities:StudentLoans"
        elif 'auto loan' in cat_lower or 'car loan' in cat_lower or 'vehicle loan' in cat_lower:
            liability_account = "Liabilities:AutoLoan"
        elif 'heloc' in cat_lower:
            liability_account = f"Liabilities:HELOC:{institution}"
        # Then check description
        elif 'ford credit' in desc_lower:
            # FORD CREDIT is an auto loan servicer
            liability_account = "Liabilities:AutoLoan"
        elif 'us bank' in desc_lower:
            # US BANK is commonly a mortgage servicer
            # Future v2: Could extract servicer from description: "Liabilities:Mortgage:USBank"
            liability_account = "Liabilities:Mortgage"
        elif 'student loan' in desc_lower:
            liability_account = "Liabilities:StudentLoans"
        elif 'mortgage' in desc_lower:
            liability_account = "Liabilities:Mortgage"
        elif 'auto loan' in desc_lower or 'car loan' in desc_lower or 'vehicle loan' in desc_lower:
            liability_account = "Liabilities:AutoLoan"
        elif 'heloc' in desc_lower:
            liability_account = f"Liabilities:HELOC:{institution}"
        elif 'loan' in cat_lower:
            # Generic loan payment
            liability_account = "Liabilities:Loans"
        else:
            # Default to mortgage if category contains "Mortgage" (case-insensitive check)
            if category and ('mortgage' in category.lower() or 'Mortgage' in category):
                liability_account = "Liabilities:Mortgage"
            else:
                # Default to student loans if description contains loan-related terms
                liability_account = "Liabilities:StudentLoans"
        
        checking_ledger = get_ledger_account(account_name, 'checking')
        postings.append((checking_ledger, amount))  # Negative from checking
        postings.append((liability_account, -amount))  # Positive to liability (reduces liability)
    
    elif transaction_type == 'credit_card_payment':
        # Credit card payment: Assets:Checking -> Liabilities:CreditCards:...
        # Amount is negative (money going out of checking)
        credit_card_ledger = get_ledger_account(account_name, 'credit_card')
        checking_ledger = get_ledger_account(source_account_name or account_name, 'checking')
        postings.append((checking_ledger, amount))  # Negative from checking
        postings.append((credit_card_ledger, -amount))  # Positive to credit card (reduces liability)
    
    elif transaction_type == 'expense':
        # Expense: Assets:Checking -> Expenses:Category
        # Amount is negative (money going out)
        expense_account = f"Expenses:{category or 'Uncategorized'}"
        asset_ledger = get_ledger_account(account_name)
        postings.append((asset_ledger, amount))  # Negative from asset
        postings.append((expense_account, -amount))  # Positive to expense (increases expense)
    
    elif transaction_type == 'income':
        # Income: Income:Source -> Assets:Checking
        # Amount is positive (money coming in)
        income_account = f"Income:{category or 'Uncategorized'}"
        asset_ledger = get_ledger_account(account_name)
        postings.append((income_account, -amount))  # Negative from income (reduces income liability)
        postings.append((asset_ledger, amount))  # Positive to asset
    
    else:
        # Unknown transaction - default to expense for personal finance (most common case)
        # For negative amounts (money going out), treat as expense
        # For positive amounts (money coming in), treat as income
        account_ledger = get_ledger_account(account_name)
        if amount < 0:
            # Money going out - likely an expense
            # For credit cards, this increases the liability (negative amount = spending)
            # For checking/savings, this decreases the asset
            expense_account = f"Expenses:{category or 'Unknown'}"
            postings.append((account_ledger, amount))  # Negative from account (asset or liability)
            postings.append((expense_account, -amount))  # Positive to expense
        else:
            # Money coming in - likely income
            # For credit cards, this decreases the liability (positive amount = payment/credit)
            # For checking/savings, this increases the asset
            income_account = f"Income:{category or 'Unknown'}"
            postings.append((income_account, -amount))  # Negative from income
            postings.append((account_ledger, amount))  # Positive to account (asset or liability)
    
    return postings


def map_account_to_ledger_account(account_name: str, account_type: str, 
                                  institution: str) -> str:
    """Map account name to ledger account hierarchy.
    
    Args:
        account_name: Original account name
        account_type: Account type (checking, savings, credit_card, etc.)
        institution: Institution name
        
    Returns:
        Ledger account path (e.g., Assets:BankOfAmerica:Checking)
    """
    # Normalize institution name
    institution_clean = institution.replace(' ', '').replace('_', '')
    
    # Map account types to ledger categories
    if account_type in ['checking', 'savings', 'cd']:
        category = 'Assets'
        type_map = {
            'checking': 'Checking',
            'savings': 'Savings',
            'cd': 'CDs'
        }
        account_subtype = type_map.get(account_type, 'Bank')
        return f"{category}:{institution_clean}:{account_subtype}"
    
    elif account_type == 'credit_card':
        return f"Liabilities:CreditCards:{institution_clean}"
    
    elif account_type in ['mortgage', 'heloc']:
        type_map = {
            'mortgage': 'Mortgage',
            'heloc': 'HELOC'
        }
        return f"Liabilities:{type_map[account_type]}:{institution_clean}"
    
    elif account_type in ['brokerage', 'ira_traditional', 'ira_roth', 'ira_rollover', 
                          '401k', '529', 'able']:
        category = 'Assets'
        type_map = {
            'brokerage': 'Investments:Brokerage',
            'ira_traditional': 'Investments:IRA:Traditional',
            'ira_roth': 'Investments:IRA:Roth',
            'ira_rollover': 'Investments:IRA:Rollover',
            '401k': 'Investments:401k',
            '529': 'Investments:529',
            'able': 'Investments:ABLE'
        }
        return f"{category}:{type_map.get(account_type, 'Investments')}:{institution_clean}"
    
    else:
        return f"Assets:{institution_clean}:{account_type}"


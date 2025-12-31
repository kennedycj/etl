"""Extract HELOC transactions from PDF and save to CSV for inspection."""

from pathlib import Path
import pandas as pd
from finance_app.agents.ledger.heloc_processor import extract_heloc_transactions_from_pdf

if __name__ == "__main__":
    heloc_dir = Path('C:/Users/19527/Documents/finance_archive/00_raw/bank/us_bank/heloc')
    output_csv = heloc_dir / "heloc_extracted_transactions.csv"
    
    print("="*70)
    print("Extracting HELOC Transactions from PDF")
    print("="*70)
    
    pdf_files = list(heloc_dir.glob('*.pdf'))
    if not pdf_files:
        print(f"No PDF files found in {heloc_dir}")
        exit(1)
    
    all_transactions = []
    
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")
        transactions = extract_heloc_transactions_from_pdf(pdf_file)
        
        if transactions:
            print(f"  Extracted {len(transactions)} transactions")
            for tx in transactions:
                tx['source_pdf'] = pdf_file.name
            all_transactions.extend(transactions)
        else:
            print(f"  No transactions extracted")
    
    if not all_transactions:
        print("\nNo transactions extracted. Check PDF format.")
        exit(1)
    
    # Create DataFrame
    df = pd.DataFrame(all_transactions)
    
    # Sort by date
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Calculate running balance (assuming starting balance is needed)
    # For now, just show the transactions
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    
    # Save to CSV
    output_df = df[['date_str', 'description', 'amount', 'source_pdf']].copy()
    output_df.columns = ['date', 'description', 'amount', 'source_pdf']
    output_df.to_csv(output_csv, index=False)
    
    print(f"\n{'='*70}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*70}")
    print(f"Total transactions extracted: {len(df)}")
    print(f"Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"\nAmount summary:")
    print(f"  Total positive (advances/charges): ${df[df['amount'] > 0]['amount'].sum():,.2f}")
    print(f"  Total negative (payments): ${df[df['amount'] < 0]['amount'].sum():,.2f}")
    print(f"  Net: ${df['amount'].sum():,.2f}")
    print(f"\nSaved to: {output_csv}")
    
    print(f"\nFirst 20 transactions:")
    print(output_df.head(20).to_string(index=False))
    
    print(f"\nLast 20 transactions:")
    print(output_df.tail(20).to_string(index=False))


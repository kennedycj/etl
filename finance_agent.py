"""Financial Agent - Orchestrates analysis and provides recommendations."""

import sys
from datetime import datetime, timedelta
from finance_app.database.connection import create_database_engine, get_session
from finance_app.agents.analyzer import FinancialAnalyzer


class FinancialAgent:
    """Agentic system for financial management and optimization."""
    
    def __init__(self, database_url: str):
        self.engine = create_database_engine(database_url)
        self.session = get_session(self.engine)
        self.analyzer = FinancialAnalyzer(self.session)
    
    def get_financial_overview(self) -> dict:
        """Get comprehensive financial overview."""
        print("🔍 Analyzing your financial situation...")
        
        overview = {
            "account_summary": self.analyzer.get_account_summary(),
            "net_worth": self.analyzer.get_net_worth(),
            "unreconciled": self.analyzer.get_unreconciled_transactions(),
            "current_month_spending": self.analyzer.get_spending_by_category(
                start_date=datetime.now().replace(day=1)
            )
        }
        
        return overview
    
    def generate_insights(self) -> list:
        """Generate actionable insights."""
        insights = []
        
        # Net worth analysis
        net_worth = self.analyzer.get_net_worth()
        if net_worth["net_worth"] < 0:
            insights.append({
                "priority": "high",
                "category": "net_worth",
                "message": f"⚠️ Your net worth is negative (${net_worth['net_worth']:,.2f}). Focus on paying down debt.",
                "recommendation": "Prioritize high-interest debt repayment"
            })
        
        # Unreconciled transactions
        unreconciled = self.analyzer.get_unreconciled_transactions()
        if unreconciled["needs_attention"] > 0:
            insights.append({
                "priority": "medium",
                "category": "reconciliation",
                "message": f"📋 You have {unreconciled['needs_attention']} transactions needing reconciliation",
                "recommendation": "Review and reconcile pending/unreconciled transactions"
            })
        
        # Spending analysis
        spending = self.analyzer.get_spending_by_category()
        if spending:
            top_category = min(spending.items(), key=lambda x: x[1]["total"])
            if top_category[1]["total"] < -1000:  # More than $1000 in a category
                insights.append({
                    "priority": "medium",
                    "category": "spending",
                    "message": f"💰 Largest spending category: {top_category[0]} (${abs(top_category[1]['total']):,.2f})",
                    "recommendation": f"Review {top_category[0]} spending for optimization opportunities"
                })
        
        return insights
    
    def identify_gaps(self) -> dict:
        """Identify gaps in current system capabilities."""
        gaps = {
            "missing_capabilities": [],
            "recommended_features": []
        }
        
        # Check for missing data
        accounts = self.analyzer.get_account_summary()
        if accounts["total_accounts"] == 0:
            gaps["missing_capabilities"].append("No accounts found - need account setup")
        
        # Check for budget data
        gaps["missing_capabilities"].append("Budget tracking - no budget vs actual comparison")
        gaps["missing_capabilities"].append("Goal setting - no savings/debt payoff goals")
        gaps["missing_capabilities"].append("Bill reminders - no automated bill tracking")
        gaps["missing_capabilities"].append("Recurring transaction detection - no pattern recognition")
        
        # Recommended features
        gaps["recommended_features"].extend([
            "Automated categorization improvements",
            "Cash flow forecasting",
            "Investment performance tracking",
            "Tax optimization suggestions",
            "Debt payoff strategies",
            "Emergency fund recommendations",
            "Retirement planning calculations"
        ])
        
        return gaps
    
    def run_analysis(self):
        """Run comprehensive analysis and report."""
        print("\n" + "="*60)
        print("🤖 FINANCIAL AGENT ANALYSIS REPORT")
        print("="*60 + "\n")
        
        # Overview
        overview = self.get_financial_overview()
        
        print("📊 FINANCIAL OVERVIEW")
        print("-" * 60)
        print(f"Total Accounts: {overview['account_summary']['total_accounts']}")
        print(f"\nNet Worth: ${overview['net_worth']['net_worth']:,.2f}")
        print(f"  Assets: ${overview['net_worth']['assets']:,.2f}")
        print(f"  Liabilities: ${overview['net_worth']['liabilities']:,.2f}")
        
        # Accounts
        print(f"\n📁 ACCOUNTS BY TYPE")
        for acc_type, count in overview['account_summary']['by_type'].items():
            print(f"  {acc_type}: {count}")
        
        # Spending
        if overview['current_month_spending']:
            print(f"\n💸 CURRENT MONTH SPENDING")
            for category, data in sorted(overview['current_month_spending'].items(), 
                                        key=lambda x: x[1]['total'])[:5]:
                print(f"  {category}: ${abs(data['total']):,.2f} ({data['count']} transactions)")
        
        # Insights
        insights = self.generate_insights()
        if insights:
            print(f"\n💡 INSIGHTS & RECOMMENDATIONS")
            for insight in insights:
                priority_icon = "🔴" if insight['priority'] == 'high' else "🟡"
                print(f"{priority_icon} {insight['message']}")
                print(f"   → {insight['recommendation']}")
        
        # Gaps
        gaps = self.identify_gaps()
        print(f"\n🔧 SYSTEM CAPABILITY GAPS")
        print("-" * 60)
        for gap in gaps['missing_capabilities'][:5]:
            print(f"  ⚠️  {gap}")
        
        print(f"\n🚀 RECOMMENDED FEATURES")
        for feature in gaps['recommended_features'][:5]:
            print(f"  • {feature}")
        
        print("\n" + "="*60 + "\n")
        
        return {
            "overview": overview,
            "insights": insights,
            "gaps": gaps
        }
    
    def close(self):
        """Close database session."""
        self.session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python finance_agent.py <database_url>")
        print('Example: python finance_agent.py "postgresql://user:pass@localhost/finance"')
        sys.exit(1)
    
    database_url = sys.argv[1]
    agent = FinancialAgent(database_url)
    
    try:
        agent.run_analysis()
    finally:
        agent.close()


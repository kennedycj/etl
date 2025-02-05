from datetime import datetime

import pytest
import ledger
@pytest.fixture()
def setup_accounts():
    asset_account = ledger.Account(name="ASSETS", type=ledger.Type.ASSETS)
    liability_account = ledger.Account(name="LIABILITIES", type=ledger.Type.LIABILITIES)
    income_account = ledger.Account(name="INCOME", type=ledger.Type.INCOME)
    expense_account = ledger.Account(name="EXPENSES", type=ledger.Type.EXPENSES)
    equity_account = ledger.Account(name="EQUITY", type=ledger.Type.EQUITY)
    yield asset_account, liability_account, income_account, expense_account, equity_account
@pytest.fixture()
def setup_block():
    block = ledger.Block()
    yield block
def test_close(setup_block, setup_accounts):
    asset_account, liability_account, income_account, expense_account, equity_account = setup_accounts
    assert setup_block.closed == datetime.max
    assert setup_block.is_closed() == False

    setup_block.close()
    assert setup_block.opened <= setup_block.closed
    assert setup_block.is_closed() == True

    with pytest.raises(ValueError):
        setup_block.entry(liability_account, 100)

def test_block_post(setup_block, setup_accounts):
    asset_account, liability_account, income_account, expense_account, equity_account = setup_accounts
    # test exception raised without passing Account object

    assert setup_block.count() == 0
    setup_block.entry(liability_account, 100)
    setup_block.entry(asset_account, 100)
    assert setup_block.count() == 2
    # test entry to DEBIT to ASSET account
    setup_block.entry(asset_account, -10)
    setup_block.entry(equity_account, -10)
    assert setup_block.count() == 4
    # test more than two entries
    setup_block.entry(asset_account, 1000)
    setup_block.entry(liability_account, 100)
    setup_block.entry(equity_account, 900)
    assert setup_block.count() == 7
    # test single entry
    setup_block.entry(liability_account, 100)
    assert setup_block.count() == 8

def test_block_close(setup_block, setup_accounts):
    asset_account, liability_account, income_account, expense_account, equity_account = setup_accounts
    setup_block.entry(liability_account, 100)
    with pytest.raises(ValueError):
        setup_block.close()

    setup_block.entry(asset_account, 1000)
    assert setup_block.is_closed() == False
    setup_block.close()
    assert setup_block.is_closed() == True
    print("Balance = {}".format(setup_block.balance()))
def test_account():
    account = ledger.Account()
    assert account.single_entry == True

from datetime import datetime, timezone
import uuid
from enum import Enum
import numpy as np
import pandas as pd

class Ledger:
    def __init__(self, id=uuid.uuid4(), name='', opened=datetime.now(timezone.utc), single_entry=False):
        self.id = id
        self.name = name
        self.opened = opened
        self.single_entry = single_entry

        self.journal = pd.DataFrame(columns=["Account", "Amount"])
    def post(self, block):
        if type(block) != Block:
            raise TypeError("expected Block type")

        if block.closed == datetime.max:
            raise ValueError("cannot add unclosed block to ledger {}".format(self.id))

        self.journal = pd.concat([self.journal, block], ignore_index=True)

    def net(self) -> None:
        return None

    def load_from_database(self) -> None:
        return None

    def load_from_file(self) -> None:
        return None
    def save_to_database(self) -> None:
        return None

    def save_to_file(self) -> None:
        return None

class Block(Ledger):
    def __init__(self, id=uuid.uuid4(), name='', opened=datetime.now(timezone.utc)):
        Ledger.__init__(self, id, name, opened)
        self.closed = datetime.max

    def is_closed(self) -> bool:
        return self.closed.replace(tzinfo=None) < datetime.max

    def post(self, account, amount):
        if self.is_closed():
            raise ValueError("cannot add posting to closed transaction {}".format(self.id))

        new_entry = pd.DataFrame([{"Account" : account, "Amount" : amount}], index=[0])
        print("new entry = {}".format(new_entry))
        self.journal = pd.concat([self.journal, new_entry], ignore_index=True)
        print("{} rows".format(len(self.journal)))
        print("column names = {}".format(list(self.journal)))
    def count(self) -> int:
        return len(self.journal)
    def balance(self) -> float:
        sum = 0
        for index, row in self.journal.iterrows():
            sum += row["Account"].type.value * row["Amount"]
            print("posting = {} : sum = {}".format(row["Account"], sum))

        return sum
    def close(self, overdraft_account=None):
        if not self.single_entry and len(self.journal) == 1:
            raise ValueError("block {} is multi-entry with only one posting".format(self.id))

        balance = self.balance()
        print("BALANCE AT CLOSE = {}".format(balance))
        if balance != 0:
            if overdraft_account == None:
                overdraft_account = Account(name="OVERDRAFT", type=Type.LIABILITIES)

            if Transaction(overdraft_account.type.value) == Transaction(np.sign(balance)):
                print("Txn({}) Txn({})".format(overdraft_account.type.value, np.sign(balance)))
                balance = -1 * balance

            self.post(overdraft_account, balance)

        print("BALANCE AFTER REMEDY = {}".format(self.balance()))
        print("PRINTING JOURNAL")
        print("{} rows".format(self.journal.shape[0]))
        for index, row in self.journal.iterrows():
           print("account = {} amount = {}".format(row["Account"], row["Amount"]))

        self.closed = datetime.now(timezone.utc)
class Transaction(Enum):
    CREDIT = 1
    DEBIT = -1
class Type(Enum):
    ASSETS = 1
    LIABILITIES = -1
    INCOME = -1
    EXPENSES = 1
    EQUITY = -1
class Account(Block):
    def __init__(self, id=uuid.uuid4(), name='', created=datetime.now(timezone.utc), type=Type.ASSETS):
        Block.__init__(self, id, name, created)
        self.single_entry = True
        self.type = type




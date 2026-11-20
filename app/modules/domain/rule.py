from decimal import Decimal
from app.errors import DataError
from .values import whole


def evaluate(row):
    stock = whole(row['上机纸张'],0,1000000)
    imposed = whole(row['刀版拼数'],1,64)
    setup = whole(row['上机废纸'],0,stock)
    gross = (stock-setup)*imposed
    spoiled = whole(row['裁切废件'],0,gross)
    batch = whole(row['每包张数'],1,1000000)
    good = gross-spoiled
    packs, tail = divmod(good,batch)
    return Decimal(good), [('裁切前件数',gross,'张'), ('整包',packs,'包'), ('尾包余量',tail,'张')]

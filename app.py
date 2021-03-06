import binascii
import requests
import rlp
import json
from ethereum import transactions, utils

from flask import Flask, request
from flask_restful import Resource, Api
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
from neo_sign import sign_context, PRIVATE
import bitcoin

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://lastwill_sign:lastwill_sign@localhost/lastwill_sign'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['USERNAME'] = 'lastwill_sign'
app.config['PASSWORD'] = 'lastwill_sign'
db = SQLAlchemy(app)

from models import Account

def reset_curve_to_eth():
    # this is standart btc/eth params for curve
    # this function reset it because 1) this params is global in bitcoin-1.1.42 lib and 2) this params are changing in neo KeyPair init
    P = 2**256 - 2**32 - 977 
    N = 115792089237316195423570985008687907852837564279074904382605163141518161494337
    A = 0 
    B = 7 
    Gx = 55066263022277343669578718895168534326250603453777594175500187360389116729240
    Gy = 32670510020758816978083085130507043184471273380659243275938904335757337482424
    bitcoin.change_curve(P, N, A, B, Gx, Gy)

class Signer(Resource):
    def post(self):
        req = request.get_json()
        source = req['source']
        dest = req.get('dest', '')
        value = req.get('value', 0)
        data = binascii.unhexlify(req.get('data', ''))
        network = req.get('network', '')
        print('signer network', network, flush=True)
        if network in ['ETHEREUM_MAINNET', 'ETHEREUM_ROPSTEN']:
            print('eth', flush=True)
            gasprice = 20 * 10 ** 9
        if network in ['RSK_MAINNET', 'RSK_TESTNET']:
            print('rsk', flush=True)
            gasprice = 1 * 10 ** 9
        if network == '':
            gasprice = 1 * 10 ** 9
        gaslimit = req.get('gaslimit', 10 ** 6) # 10 ** 6 is suitable for deploy
        account = db.session.query(Account).filter(Account.addr==source).limit(1).with_for_update().one()
        priv = binascii.unhexlify(account.priv)
        nonce = req['nonce']
        reset_curve_to_eth()
        tx = transactions.Transaction(nonce, gasprice, gaslimit, dest, value, data).sign(priv)
        raw_tx = binascii.hexlify(rlp.encode(tx))
        return {'result': raw_tx.decode()}


class KeyManager(Resource):
    def post(self):
        try:
            account = db.session.query(Account).filter(Account.used==False).limit(1).with_for_update().one()
        except NoResultFound:
            return {'status': 1, 'message': 'NoResultFound'}
        account.used = True
        db.session.add(account)
        db.session.commit()
        return {'status': 0, 'addr': account.addr}

class NeoSign(Resource):
    def post(self):
        priv = PRIVATE[request.get_json()['address']]
        return sign_context(request.get_json()['binary_tx'], priv)


api = Api(app)
api.add_resource(Signer, '/sign/')
api.add_resource(KeyManager, '/get_key/')
api.add_resource(NeoSign, '/neo_sign/')

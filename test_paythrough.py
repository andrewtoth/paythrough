import math
import os
import unittest
from pyln.client import RpcError
from pyln.testing.fixtures import *
from pyln.testing.utils import DEVELOPER, wait_for

plugin_path = os.path.join(os.path.dirname(__file__), 'paythrough.py')

def test_paythrough_starts(node_factory):
    l1 = node_factory.get_node()
    # Test dynamically
    l1.rpc.plugin_start(plugin_path)
    l1.daemon.wait_for_log('Plugin paythrough initialized')
    l1.rpc.plugin_stop(plugin_path)
    l1.rpc.plugin_start(plugin_path)
    l1.daemon.wait_for_log('Plugin paythrough initialized')
    l1.stop()
    # Then statically
    l1.daemon.opts['plugin'] = plugin_path
    l1.start()
    # Start at 0 and 're-await' the two inits above. Otherwise this is flaky.
    l1.daemon.logsearch_start = 0
    l1.daemon.wait_for_logs(["Plugin paythrough initialized",
                             "Plugin paythrough initialized",
                             "Plugin paythrough initialized"])
    l1.rpc.plugin_stop(plugin_path)

def get_peer(node, id):
    return node.rpc.listpeers(id)['peers'][0]['channels'][0]

def has_spendable(node, id):
    p = get_peer(node, id)
    return str(p['spendable_msat']) != '0msat' and str(p['receivable_msat']) != '0msat'

def roundup(x):
    return int(math.ceil(int(x) / 100.0)) * 100

@unittest.skipIf(not DEVELOPER, "Too slow without fast gossip")
def test_paythrough_paythrough(capsys, node_factory):
    l1, l2, l3, l4 = node_factory.line_graph(4, opts=[{ 'plugin': plugin_path }, {}, {}, {}], wait_for_announce=True)
    nodes = [l1, l2, l3, l4]
    ids = list(map(lambda node: node.rpc.getinfo()['id'], nodes))

    # Pay half channel capacity from l2->l3 and l3->l4 so they have balanced
    # capacity and can route
    msats = round(5e8)
    invoice = l3.rpc.invoice(msats, 'label', 'desc')
    l2.rpc.pay(invoice['bolt11'])

    invoice = l4.rpc.invoice(msats, 'label', 'desc')
    l3.rpc.pay(invoice['bolt11'])

    # Wait until the payments are settled so they can route
    wait_for(lambda: has_spendable(l3, ids[1]) and has_spendable(l4, ids[2]))

    # Create channels l1->l3 and l1->l4 to test alternate routing from l1->l2
    node_factory.join_nodes([l1, l3])
    node_factory.join_nodes([l1, l4])

    scid12 = l1.rpc.listpeers(ids[1])['peers'][0]['channels'][0]['short_channel_id']
    scid13 = l1.rpc.listpeers(ids[2])['peers'][0]['channels'][0]['short_channel_id']
    scid14 = l1.rpc.listpeers(ids[3])['peers'][0]['channels'][0]['short_channel_id']

    msats = round(5e7)

    # Pay l1->l2 directly
    invoice = l2.rpc.invoice(msats, 'label1', 'desc')
    resp = l1.rpc.paythrough(invoice['bolt11'], scid12)
    assert 'status' in resp and resp['status'] == 'complete', 'Payment through node 2 failed'
    # Wait for payment to settle before checking channel balances
    wait_for(lambda: has_spendable(l2, ids[0]))
    p = get_peer(l1, ids[1])
    assert p['spendable_msat'] == 916504000, 'Payment went through different channel1'

    # Pay l1->l3->l2
    invoice = l2.rpc.invoice(msats, 'label2', 'desc')
    resp = l1.rpc.paythrough(invoice['bolt11'], scid13)
    assert 'status' in resp and resp['status'] == 'complete', 'Payment through node 3 failed'
    # Wait for payment to settle before checking channel balances
    wait_for(lambda: has_spendable(l3, ids[0]))
    p = get_peer(l1, ids[2])
    assert roundup(p['spendable_msat']) == 916503500, 'Payment went through different channel2' + str(p['spendable_msat'])
    p = get_peer(l3, ids[1])
    assert p['spendable_msat'] == 440000000, 'Payment went through different channel3' + str(p['spendable_msat'])

    # Pay l1->l4->l3->l2
    invoice = l2.rpc.invoice(msats, 'label3', 'desc')
    resp = l1.rpc.paythrough(invoice['bolt11'], scid14)
    assert 'status' in resp and resp['status'] == 'complete', 'Payment through node 4 failed'
    # Wait for payment to settle before checking channel balances
    wait_for(lambda: has_spendable(l4, ids[0]))
    p = get_peer(l1, ids[3])
    assert roundup(p['spendable_msat']) == 916503000, 'Payment went through different channel4' + str(p['spendable_msat'])
    p = get_peer(l4, ids[2])
    assert roundup(p['spendable_msat']) == 439999500, 'Payment went through different channel5' + str(p['spendable_msat'])
    p = get_peer(l3, ids[1])
    assert p['spendable_msat'] == 390000000, 'Payment went through different channel6' + str(p['spendable_msat'])

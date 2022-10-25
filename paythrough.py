#!/usr/bin/env python3
'''Pay through a specific channel
'''
from pyln.client import Plugin
from pyln.client.lightning import RpcError

plugin = Plugin()

@plugin.init()
def init(options: dict, configuration: dict, plugin: Plugin, **kwargs):
    plugin.log('Plugin paythrough initialized')
    return {}

@plugin.method('paythrough')
def paythrough(plugin, bolt11, scid, msatoshi=None, label=None, riskfactor=None,
                maxfeepercent=None, retry_for=None, maxdelay=None,
                exemptfee=None):
    """Pay a bolt11 invoice through a specific channel,
    even if better/cheaper routes exist through other channels.
    All parameters after scid are identical to pay except exclude. These will
    all be forwarded to pay via this plugin.
    """
    peers = plugin.rpc.listpeers()['peers']
    channels = list(map(lambda peer: peer['channels'], peers))
    channels = [item for sublist in channels for item in sublist]
    channels = list(filter(lambda channel:
                    channel['state'] == 'CHANNELD_NORMAL', channels))
    channels_length = len(channels)
    channels = list(filter(lambda channel: channel['short_channel_id'] != scid,
                    channels))
    
    if len(channels) != channels_length-1: # We should have one less channel
        return { 'code': -1, 
                'message': f'Short channel id {scid} is not valid' }

    scids = list(map(lambda channel: 
        f"{channel['short_channel_id']}/{channel['direction']}", channels))

    try:
        resp = plugin.rpc.pay(bolt11=bolt11, msatoshi=msatoshi, label=label,
            riskfactor=riskfactor, maxfeepercent=maxfeepercent,
            retry_for=retry_for, maxdelay=maxdelay, exemptfee=exemptfee,
            exclude=scids)
        return resp
    except RpcError as e:
        return e.error

plugin.run()

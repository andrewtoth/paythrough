# paythrough

This plugin adds the ability to pay a bolt11 invoice through a specific channel,
even if a better/cheaper route exists through a different channel. A new RPC,
`paythrough`, is defined which takes the same arguments as `pay`, except the
second argument is `scid` which is the short-channel-id of the channel you wish
to pay through. This leverages the `exclude` argument on `pay`, so that argument
is removed.

This can be useful for keeping channels balanced or otherwise managing liquidity
when you will be paying for something through lightning anyways.

"""RKE/1.0 (RAIDA Group 15) constants.

Values fixed by specs/rke-1.0.md; RKE bodies are big-endian and end with the RAIDA
`3E 3E` trailer. The RAIDA request/response header and the encryption envelope are
defined by the RAIDA protocol and are out of scope here (referenced, not redefined).
"""

# RAIDA command group and the two Group 15 command codes (§4.1).
COMMAND_GROUP = 15
CMD_PRELOAD_MASTER_KEY = 0x01   # content server -> RAIDA (stage material)
CMD_GET_KEY_SHARE = 0x02        # client -> RAIDA (retrieve a share)

# CloudCoin coin type / network id (§4.2), shared with CBDF mailboxes and DRD.
CLOUDCOIN_COIN_TYPE = 0x0006

# Fixed field sizes (§4.2 / §4.3 / §4.4).
PREAMBLE_LEN = 48
CHALLENGE_LEN = 16
SESSION_ID_LEN = 8
AN_LEN = 16
MASTER_SECRET_LEN = 32
GET_KEY_SHARE_CSID_LEN = 16     # fixed 16 bytes in get_key_share (variable in preload)
CLIENT_SN_LEN = 5

# RAIDA encryption envelope types each command accepts (§4.5) — informational; the
# envelope itself belongs to the RAIDA protocol layer.
PRELOAD_ENVELOPES = (0, 1)
GET_KEY_SHARE_ENVELOPES = (0, 1, 5)

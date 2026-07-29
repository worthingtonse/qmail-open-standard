# Registries

Machine-readable source for the registries defined by the specs, kept separate
from prose so entries can be reviewed and consumed programmatically.

Planned registries (each spec defines its own in its §6 IANA/registry section):

| Registry                | Defined by | Default allocation policy |
|-------------------------|------------|---------------------------|
| CBDF type-tag registry  | CBDF/1.0   | Specification Required    |
| RKE cipher-suite registry | RKE/1.0  | Specification Required    |
| DRD record-type registry| DRD/1.0    | Specification Required    |
| QMail header/field registry (if needed) | QMail/1.0 | Specification Required |

Also to reserve with IANA (not repo-local registries, but tracked here):

- URI scheme `qmail:`
- Media types `application/qmail`, `application/cbdf`
- TCP/UDP port(s) for any QMail/RKE/DRD own-transport

> TODO: choose a machine-readable format (CSV or JSON) and add one file per
> registry, e.g. `cbdf-type-registry.csv`, once CBDF/1.0 §4.3 defines its tags.

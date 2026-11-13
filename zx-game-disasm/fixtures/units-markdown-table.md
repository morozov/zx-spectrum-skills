# SkoolKit tables

The paragraph before a table ends where the table starts. #TABLE(default)
{ =h Address | =h Label             | =h Holds          }
{ $BD3C      | `shields`            | Shields left      }
{ $BD40      | `device_destroyed_1` | Sector 1 device   }
{ $BD41      | `device_destroyed_2` | Sector 2 device   }
{ $C0AC      | `image_buffers`      | From $5B00        }
{ $FA00      | `mirror`             | $FA00–$FCFF       }
TABLE#

A paragraph after the table is a unit of its own, and names $BD3C and $BD40.

```
{ $8000 | a fenced row | stays out }
```

A table that opens on a line of its own, as a spec page writes it:

#TABLE(default)
{ =h Page            | =h What it covers                    }
{ [State](state.md)  | The `lives` counter and `main_loop`  }
TABLE#

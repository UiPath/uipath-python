from dataclasses import dataclass

import click


@dataclass
class ResourceImportSummary:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    virtual_created: int = 0
    virtual_existing: int = 0
    not_found: int = 0

    @property
    def total(self) -> int:
        return (
            self.created
            + self.updated
            + self.unchanged
            + self.virtual_created
            + self.virtual_existing
            + self.not_found
        )

    def __str__(self) -> str:
        return (
            f"\n \U0001f535 Resource import summary: {self.total} total resources - "
            f"{click.style(str(self.created), fg='green')} created, "
            f"{click.style(str(self.updated), fg='blue')} updated, "
            f"{click.style(str(self.unchanged), fg='yellow')} unchanged, "
            f"{click.style(str(self.virtual_created), fg='green')} virtual-created, "
            f"{click.style(str(self.virtual_existing), fg='yellow')} virtual-existing, "
            f"{click.style(str(self.not_found), fg='red')} not found"
        )

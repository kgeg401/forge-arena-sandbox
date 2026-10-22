"""Owned Arena identity helpers. Catalogue presence is not release or legality."""
import html
import re


def clean_name(name):
    # This sprite carries identity: stripping it would merge A-The One Ring
    # into the paper card and silently pick a different rules implementation.
    name = re.sub(r'<sprite\b[^>]*\bname=[\"\']arena_a[\"\'][^>]*>', 'A-', name, flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', '', name)).strip()


def indexed_printings(rows):
    """Primary entries plus rebalanced versions of a source primary entry.

    LinkedFaceGrpIds is bidirectional and cannot identify the deck-facing side.
    The owned database links every current rebalanced row back to its original
    through DefunctRebalancedCardGrpId. Only source-primary counterparts enter
    the deck catalogue; adventure/back faces remain linked metadata.
    """
    result = []
    for row in rows.values():
        if row['IsToken']:
            continue
        primary = bool(row['IsPrimaryCard'])
        counterpart = rows.get(row.get('DefunctRebalancedCardGrpId', 0))
        rebalanced_primary = bool(row['IsRebalanced'] and counterpart and counterpart['IsPrimaryCard'] and not counterpart['IsToken'])
        if primary or rebalanced_primary:
            result.append(row)
    return result

*** Settings ***
Documentation    Deck import: catalogue, valid/invalid lists, and playing an imported deck.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Card Catalogue Exposes Battle-Ready Cards And A Sample
    ${r}=    GET On Session    tcg    /api/cards/catalog
    Should Not Be Empty    ${r.json()}[cards]
    Should Not Be Empty    ${r.json()}[sample_decklist]

Importing The Sample Decklist Succeeds
    ${sample}=    Get Sample Decklist
    ${deck_id}=    Import Deck    Imported Zard    ${sample}
    Should Not Be Empty    ${deck_id}

Imported Deck Appears In The Deck List
    ${sample}=    Get Sample Decklist
    ${deck_id}=    Import Deck    Listed Deck    ${sample}
    ${decks}=    GET On Session    tcg    /api/decks
    Should Contain    ${decks.json()}[decks]    ${deck_id}

Imported Deck Is Playable
    ${sample}=    Get Sample Decklist
    ${deck_id}=    Import Deck    Playable Deck    ${sample}
    ${gid}=    New AI Game    deck_a=${deck_id}    deck_b=gardevoir_ex
    ${r}=    Play AI Game To End    ${gid}
    Should Be True    ${r}[done]

Unknown Cards Are Reported Not Silently Dropped
    ${body}=    Create Dictionary    name=Bad Deck    list=3 Pikachu ex\n2 Charmander
    ${r}=    POST On Session    tcg    /api/decks/import    json=${body}
    Should Not Be True    ${r.json()}[ok]
    Should Not Be Empty    ${r.json()}[unknown]

Empty Decklist Is Rejected
    ${body}=    Create Dictionary    name=Empty    list=${EMPTY}
    ${r}=    POST On Session    tcg    /api/decks/import    json=${body}
    Should Not Be True    ${r.json()}[ok]
    Should Not Be Empty    ${r.json()}[errors]


*** Keywords ***
Get Sample Decklist
    ${r}=    GET On Session    tcg    /api/cards/catalog
    RETURN    ${r.json()}[sample_decklist]

Import Deck
    [Arguments]    ${name}    ${list}
    ${body}=    Create Dictionary    name=${name}    list=${list}
    ${r}=    POST On Session    tcg    /api/decks/import    json=${body}    expected_status=200
    Should Be True    ${r.json()}[ok]
    RETURN    ${r.json()}[deck_id]

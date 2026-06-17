*** Settings ***
Documentation    Rules feed, attribution sources, and the newly added rules-legal decks.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Rules Feed Is Served And Grouped
    ${r}=    GET On Session    tcg    /api/rules
    Should Be True    ${r.json()}[count] > 0
    Should Not Be Empty    ${r.json()}[groups]
    # a few key official rules should be represented
    ${flat}=    Evaluate    " ".join(i['rule'] for g in $r.json()['groups'] for i in g['items'])
    Should Contain    ${flat}    Weakness
    Should Contain    ${flat}    Prize
    Should Contain    ${flat}    4-copy

Sources Endpoint Carries The Image Disclaimer And Links
    ${r}=    GET On Session    tcg    /api/sources
    Should Contain    ${r.json()}[disclaimer]    no ownership
    Should Not Be Empty    ${r.json()}[links]
    ${urls}=    Evaluate    " ".join(l['url'] for l in $r.json()['links'])
    Should Contain    ${urls}    pokemon.com

New Decks Are Available
    ${decks}=    GET On Session    tcg    /api/decks
    Should Contain    ${decks.json()}[decks]    chien_pao_ex
    Should Contain    ${decks.json()}[decks]    iron_valiant_ex

New Decks Are Playable
    [Template]    Deck Plays To Completion
    chien_pao_ex      iron_valiant_ex
    chien_pao_ex      charizard_ex
    iron_valiant_ex   gardevoir_ex


*** Keywords ***
Deck Plays To Completion
    [Arguments]    ${deck_a}    ${deck_b}
    ${gid}=    New AI Game    deck_a=${deck_a}    deck_b=${deck_b}
    ${r}=    Play AI Game To End    ${gid}
    Should Be True    ${r}[done]

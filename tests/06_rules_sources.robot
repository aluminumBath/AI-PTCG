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
    Should Contain    ${decks.json()}[decks]    pecharunt_ex
    Should Contain    ${decks.json()}[decks]    lugia_ex
    Should Contain    ${decks.json()}[decks]    tapu_koko
    Should Contain    ${decks.json()}[decks]    flutter_mane_ex
    Should Contain    ${decks.json()}[decks]    terapagos_ex
    Should Contain    ${decks.json()}[decks]    dragapult_ex
    Should Contain    ${decks.json()}[decks]    eternatus_ex
    Should Contain    ${decks.json()}[decks]    gouging_fire_ex
    Should Contain    ${decks.json()}[decks]    iron_thorns_ex

Decks Carry Strategy Metadata And Images
    ${decks}=    GET On Session    tcg    /api/decks
    Should Not Be Empty    ${decks.json()}[meta]
    ${entei}=    Evaluate    [d for d in $decks.json()['meta'] if d['id']=='entei_ex'][0]
    Should Not Be Empty    ${entei}[strategy]
    Should Not Be Empty    ${entei}[key_cards]
    Should Be Equal    ${entei}[type]    Fire
    ${gho}=    Evaluate    [d for d in $decks.json()['meta'] if d['id']=='gholdengo_ex'][0]
    Should Not Be Empty    ${gho}[image]

Built-In Sets Are Listed
    ${r}=    GET On Session    tcg    /api/sets
    ${n}=    Get Length    ${r.json()}[sets]
    Should Be True    ${n} >= 13
    ${names}=    Evaluate    " ".join(s['name'] for s in $r.json()['sets'])
    Should Contain    ${names}    Obsidian Flames

New Strategy Decks Are Playable
    [Template]    Deck Plays To Completion
    pecharunt_ex      suicune_ex
    lugia_ex          tapu_koko
    flutter_mane_ex   gholdengo_ex
    raging_bolt_ex    terapagos_ex
    dragapult_ex      eternatus_ex
    gouging_fire_ex   iron_thorns_ex


*** Keywords ***
Deck Plays To Completion
    [Arguments]    ${deck_a}    ${deck_b}
    ${gid}=    New AI Game    deck_a=${deck_a}    deck_b=${deck_b}
    ${r}=    Play AI Game To End    ${gid}
    Should Be True    ${r}[done]

*** Settings ***
Documentation    Per-user favorites: add/list/remove decks, cards, and sets, with validation and auth.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Favorites Require Authentication
    GET On Session    tcg    /api/favorites    expected_status=401

Add And List Favorites Across Kinds
    ${token}    ${username}=    Register Random User
    ${h}=    Auth Headers    ${token}
    # a fresh user starts empty
    ${r}=    GET On Session    tcg    /api/favorites    headers=${h}
    Should Be Empty    ${r.json()}[decks]
    # add one of each kind
    Add Favorite    ${h}    deck    charizard_ex
    Add Favorite    ${h}    set     sv1
    Add Favorite    ${h}    card    sv1-54
    ${r}=    GET On Session    tcg    /api/favorites    headers=${h}
    Should Contain    ${r.json()}[decks]    charizard_ex
    Should Contain    ${r.json()}[sets]     sv1
    Should Contain    ${r.json()}[cards]    sv1-54

Adding A Favorite Twice Is Idempotent
    ${token}    ${username}=    Register Random User
    ${h}=    Auth Headers    ${token}
    Add Favorite    ${h}    deck    miraidon_ex
    ${r}=    Add Favorite    ${h}    deck    miraidon_ex
    ${count}=    Evaluate    $r.json()['decks'].count('miraidon_ex')
    Should Be Equal As Integers    ${count}    1

Invalid Favorites Are Rejected
    ${token}    ${username}=    Register Random User
    ${h}=    Auth Headers    ${token}
    # unknown kind
    ${bad}=    Create Dictionary    kind=pokemon    ref_id=charizard_ex
    POST On Session    tcg    /api/favorites    json=${bad}    headers=${h}    expected_status=400
    # unknown deck / set
    ${nd}=    Create Dictionary    kind=deck    ref_id=does_not_exist_ex
    POST On Session    tcg    /api/favorites    json=${nd}    headers=${h}    expected_status=404
    ${ns}=    Create Dictionary    kind=set    ref_id=sv99
    POST On Session    tcg    /api/favorites    json=${ns}    headers=${h}    expected_status=404

Removing A Favorite Works
    ${token}    ${username}=    Register Random User
    ${h}=    Auth Headers    ${token}
    Add Favorite    ${h}    deck    gardevoir_ex
    ${r}=    DELETE On Session    tcg    /api/favorites/deck/gardevoir_ex    headers=${h}    expected_status=200
    Should Not Contain    ${r.json()}[decks]    gardevoir_ex

Favorites Are Per-User
    ${t1}    ${u1}=    Register Random User
    ${t2}    ${u2}=    Register Random User
    ${h1}=    Auth Headers    ${t1}
    ${h2}=    Auth Headers    ${t2}
    Add Favorite    ${h1}    deck    lugia_ex
    ${r2}=    GET On Session    tcg    /api/favorites    headers=${h2}
    Should Not Contain    ${r2.json()}[decks]    lugia_ex


*** Keywords ***
Add Favorite
    [Arguments]    ${headers}    ${kind}    ${ref_id}
    ${body}=    Create Dictionary    kind=${kind}    ref_id=${ref_id}
    ${r}=    POST On Session    tcg    /api/favorites    json=${body}    headers=${headers}    expected_status=200
    RETURN    ${r}

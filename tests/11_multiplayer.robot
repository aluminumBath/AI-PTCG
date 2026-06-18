*** Settings ***
Documentation    Two-human multiplayer: create/join, per-seat masking, turn validation, and capture/learn endpoints.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Create And Join A Match
    ${body}=    Create Dictionary    deck_a=charizard_ex    deck_b=gardevoir_ex    mode=async    name=Alice
    ${cr}=    POST On Session    tcg    /api/multiplayer/create    json=${body}    expected_status=200
    Should Not Be Empty    ${cr.json()}[match_id]
    Should Not Be Empty    ${cr.json()}[token]
    Set Suite Variable    ${MID}    ${cr.json()}[match_id]
    Set Suite Variable    ${T0}    ${cr.json()}[token]
    ${jb}=    Create Dictionary    name=Bob
    ${jr}=    POST On Session    tcg    /api/multiplayer/${MID}/join    json=${jb}    expected_status=200
    Should Be Equal As Integers    ${jr.json()}[seat]    1
    Set Suite Variable    ${T1}    ${jr.json()}[token]

Match Becomes Active And Masks The Opponent Hand
    ${p0}=    Create Dictionary    token=${T0}
    ${st}=    GET On Session    tcg    /api/multiplayer/${MID}/state    params=${p0}
    Should Be Equal    ${st.json()}[status]    active
    Should Be Equal As Integers    ${st.json()}[your_seat]    0
    # opponent (seat 1) hand identities must be hidden (list of nulls)
    ${opp}=    Set Variable    ${st.json()}[state][players][1]
    Should Be True    ${opp}[hand_count] > 0
    Should Be Equal    ${opp}[hand][0]    ${None}
    # my own hand should be visible (first entry is a card name string)
    ${me}=    Set Variable    ${st.json()}[state][players][0]
    Should Not Be Equal    ${me}[hand][0]    ${None}

Turn Validation Is Enforced
    ${p0}=    Create Dictionary    token=${T0}
    ${st}=    GET On Session    tcg    /api/multiplayer/${MID}/state    params=${p0}
    ${cp}=    Set Variable    ${st.json()}[current_player]
    # the engine coin-flips who goes first, so resolve tokens by the actual current player
    ${cur}=    Set Variable If    ${cp} == 0    ${T0}    ${T1}
    ${other}=    Set Variable If    ${cp} == 0    ${T1}    ${T0}
    ${pc}=    Create Dictionary    token=${cur}
    ${po}=    Create Dictionary    token=${other}
    # the player who is NOT on turn cannot act
    ${bad}=    Create Dictionary    index=${0}
    POST On Session    tcg    /api/multiplayer/${MID}/action    params=${po}    json=${bad}    expected_status=403
    # out-of-range action index is rejected for the player on turn
    ${oor}=    Create Dictionary    index=${9999}
    POST On Session    tcg    /api/multiplayer/${MID}/action    params=${pc}    json=${oor}    expected_status=400
    # a legal action from the player on turn is accepted
    ${ok}=    Create Dictionary    index=${0}
    ${r}=    POST On Session    tcg    /api/multiplayer/${MID}/action    params=${pc}    json=${ok}    expected_status=200
    Should Be Equal    ${r.json()}[match_id]    ${MID}

Unknown Match Is Not Found
    GET On Session    tcg    /api/multiplayer/nope/state    expected_status=404

Learned Endpoint Reports Capture State
    ${r}=    GET On Session    tcg    /api/multiplayer/learned
    Dictionary Should Contain Key    ${r.json()}    games
    Dictionary Should Contain Key    ${r.json()}    total_samples
    Dictionary Should Contain Key    ${r.json()}    can_learn

Rematch Re-Hosts The Same Decks
    ${p0}=    Create Dictionary    token=${T0}
    ${rm}=    POST On Session    tcg    /api/multiplayer/${MID}/rematch    params=${p0}    expected_status=200
    ${newmid}=    Set Variable    ${rm.json()}[match_id]
    ${newtok}=    Set Variable    ${rm.json()}[token]
    Should Not Be Equal    ${newmid}    ${MID}
    ${np}=    Create Dictionary    token=${newtok}
    ${ns}=    GET On Session    tcg    /api/multiplayer/${newmid}/state    params=${np}
    Should Be Equal    ${ns.json()}[deck_ids][0]    charizard_ex
    Should Be Equal    ${ns.json()}[status]    waiting
    # a non-participant token cannot start a rematch
    ${bp}=    Create Dictionary    token=not-a-real-token
    POST On Session    tcg    /api/multiplayer/${MID}/rematch    params=${bp}    expected_status=403

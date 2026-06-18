*** Settings ***
Documentation    Lifetime model scoreboard: games are recorded and exportable as JSON/CSV.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Playing An AI Game Records Model Scores
    ${gid}=    New AI Game    deck_a=charizard_ex    deck_b=gardevoir_ex
    ${r}=    Play AI Game To End    ${gid}
    Should Be True    ${r}[done]
    ${s}=    GET On Session    tcg    /api/models/stats
    ${games}=    Evaluate    sum(x['games'] for x in $s.json()['stats'])
    Should Be True    ${games} > 0
    # rows carry a win rate and points
    ${first}=    Set Variable    ${s.json()}[stats][0]
    Dictionary Should Contain Key    ${first}    win_rate
    Dictionary Should Contain Key    ${first}    points

Scoreboard Exports As JSON And CSV
    ${j}=    GET On Session    tcg    /api/models/stats/export
    Should Be Equal    ${j.json()}[filename]    model_scores.json
    Should Not Be Empty    ${j.json()}[stats]
    ${csvparams}=    Create Dictionary    format=csv
    ${c}=    GET On Session    tcg    /api/models/stats/export    params=${csvparams}
    Should Contain    ${c.text}    model_id,label,games,wins,losses,draws,win_rate

Scoreboard Reset Clears Records
    ${r}=    POST On Session    tcg    /api/models/stats/reset
    Dictionary Should Contain Key    ${r.json()}    reset
    ${s}=    GET On Session    tcg    /api/models/stats
    Length Should Be    ${s.json()}[stats]    0

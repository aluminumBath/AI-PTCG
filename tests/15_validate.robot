*** Settings ***
Documentation     Result validation (confidence intervals + sanity checks) and consistency (mean ± SD).
Resource          resources/api.resource
Library           Collections
Suite Setup       Connect To API


*** Keywords ***
Wait Until Job Done
    [Arguments]    ${path}    ${tries}=160
    FOR    ${i}    IN RANGE    ${tries}
        ${r}=    GET On Session    tcg    ${path}
        ${st}=    Set Variable    ${r.json()}[status]
        Exit For Loop If    '${st}' != 'running'
        Sleep    0.3s
    END
    RETURN    ${r.json()}


*** Test Cases ***
Validate Attaches Confidence Intervals And Checks
    ${agents}=    Create List    heuristic    greedy    random
    ${decks}=    Create List    charizard_ex    gardevoir_ex
    ${body}=    Create Dictionary    agents=${agents}    decks=${decks}    games_per_pairing=${4}
    ${r}=    POST On Session    tcg    /api/tournament/run    json=${body}    expected_status=200
    ${jid}=    Set Variable    ${r.json()}[job_id]
    Wait Until Job Done    /api/tournament/${jid}
    ${v}=    GET On Session    tcg    /api/tournament/${jid}/validate    expected_status=200
    ${j}=    Set Variable    ${v.json()}
    Should Not Be Empty    ${j}[checks]
    Dictionary Should Contain Key    ${j}    verdict
    # heuristic should have a valid CI with lo <= hi and n > 0
    ${ci}=    Set Variable    ${j}[winrates][heuristic][overall]
    Should Be True    ${ci}[ci_lo] <= ${ci}[ci_hi]
    Should Be True    ${ci}[n] > 0

Validate Unknown Job Is 404
    GET On Session    tcg    /api/tournament/nope/validate    expected_status=404

Consistency Reports Mean And Standard Deviation
    ${decks}=    Create List    charizard_ex    gardevoir_ex
    ${body}=    Create Dictionary    agent_a=heuristic    agent_b=random    decks=${decks}
    ...    batches=${3}    games_per_batch=${4}    seed=${1}
    ${r}=    POST On Session    tcg    /api/validate/consistency    json=${body}    expected_status=200
    ${jid}=    Set Variable    ${r.json()}[job_id]
    ${done}=    Wait Until Job Done    /api/validate/consistency/${jid}
    Should Be Equal    ${done}[status]    done
    ${res}=    Set Variable    ${done}[result]
    Length Should Be    ${res}[per_batch]    3
    Should Be True    ${res}[std] >= 0
    Should Be True    0 <= ${res}[mean] <= 1
    Dictionary Should Contain Key    ${res}    pooled_winrate

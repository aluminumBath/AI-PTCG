*** Settings ***
Documentation    Model comparison tournaments: model catalogue, running, and standings.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Agent Catalogue Exposes Model Metadata
    ${r}=    GET On Session    tcg    /api/agents
    Should Not Be Empty    ${r.json()}[models]
    # the new model families should be present
    ${ids}=    Evaluate    [m['id'] for m in $r.json()['models']]
    Should Contain    ${ids}    minimax
    Should Contain    ${ids}    rl_mcts

Tournament With Fewer Than Two Models Is Rejected
    ${body}=    Create Dictionary    agents=${{ ['heuristic'] }}    decks=${{ ['charizard_ex'] }}    games_per_pairing=${2}
    POST On Session    tcg    /api/tournament/run    json=${body}    expected_status=400

Tournament Ranks The Models
    ${agents}=    Create List    random    heuristic    minimax
    ${decks}=    Create List    charizard_ex    gardevoir_ex
    ${body}=    Create Dictionary    agents=${agents}    decks=${decks}    games_per_pairing=${2}
    ${start}=    POST On Session    tcg    /api/tournament/run    json=${body}    expected_status=200
    ${job}=    Set Variable    ${start.json()}[job_id]
    Should Be True    ${start.json()}[total_games] > 0
    ${result}=    Wait For Tournament    ${job}
    Should Not Be Empty    ${result}[standings]
    Should Not Be Equal    ${result}[best]    ${None}
    # every selected model appears in the standings
    ${ranked}=    Evaluate    [s['agent'] for s in $result['standings']]
    Should Contain    ${ranked}    minimax

Unknown Tournament Id Is Not Found
    GET On Session    tcg    /api/tournament/nope    expected_status=404


*** Keywords ***
Wait For Tournament
    [Arguments]    ${job}    ${max_polls}=60
    FOR    ${i}    IN RANGE    ${max_polls}
        ${r}=    GET On Session    tcg    /api/tournament/${job}
        IF    '${r.json()}[status]' == 'done'    RETURN    ${r.json()}[result]
        IF    '${r.json()}[status]' == 'error'    Fail    Tournament errored: ${r.json()}[error]
        Sleep    1s
    END
    Fail    Tournament did not finish in time

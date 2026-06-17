*** Settings ***
Documentation    Skill-rating ladder: self-validation, episode runs, rating updates, and export.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Submission Self-Validates To Active With Initial Rating
    ${id}=    Create Submission    Heur-Ladder    heuristic
    Wait Until Keyword Succeeds    40x    2s    Submission Status Should Be    ${id}    active
    ${s}=    Get Submission    ${id}
    Should Be Equal As Numbers    ${s}[mu]      600
    Should Be Equal As Numbers    ${s}[sigma]   200

Episodes Update Ratings And Reduce Uncertainty
    ${a}=    Create Submission    L-Random    random
    ${b}=    Create Submission    L-Net       rl
    Wait Until Keyword Succeeds    40x    2s    Submission Status Should Be    ${a}    active
    Wait Until Keyword Succeeds    40x    2s    Submission Status Should Be    ${b}    active
    ${runbody}=    Create Dictionary    count=${14}
    ${job}=    POST On Session    tcg    /api/episodes/run    json=${runbody}
    ${jid}=    Set Variable    ${job.json()}[job_id]
    Wait Until Keyword Succeeds    90x    2s    Episode Job Done    ${jid}
    # at least one submission has now played games and shifted from the prior
    ${list}=    GET On Session    tcg    /api/submissions
    ${games}=    Evaluate    sum(s['games'] for s in $list.json()['submissions'])
    Should Be True    ${games} > 0
    ${moved}=    Evaluate    any(s['games']>0 and s['sigma']<200 for s in $list.json()['submissions'])
    Should Be True    ${moved}

Submission Pool Is Capped At Ten
    ${r}=    GET On Session    tcg    /api/submissions
    Should Be Equal As Numbers    ${r.json()}[max_active]    10

Export Produces An Agent Manifest
    ${list}=    GET On Session    tcg    /api/submissions
    ${active}=    Evaluate    [s['id'] for s in $list.json()['submissions'] if s['status']=='active']
    ${id}=    Set Variable    ${active}[0]
    ${ex}=    GET On Session    tcg    /api/submissions/${id}/export
    Should Not Be Empty    ${ex.json()}[agent][model]
    Dictionary Should Contain Key    ${ex.json()}    rating


*** Keywords ***
Create Submission
    [Arguments]    ${name}    ${agent}    ${deck}=rotating
    ${body}=    Create Dictionary    name=${name}    agent=${agent}    deck=${deck}
    ${r}=    POST On Session    tcg    /api/submissions    json=${body}    expected_status=200
    RETURN    ${r.json()}[id]

Get Submission
    [Arguments]    ${id}
    ${r}=    GET On Session    tcg    /api/submissions/${id}
    RETURN    ${r.json()}

Submission Status Should Be
    [Arguments]    ${id}    ${status}
    ${s}=    Get Submission    ${id}
    Should Be Equal    ${s}[status]    ${status}

Episode Job Done
    [Arguments]    ${jid}
    ${r}=    GET On Session    tcg    /api/episodes/status/${jid}
    Should Be Equal    ${r.json()}[status]    done

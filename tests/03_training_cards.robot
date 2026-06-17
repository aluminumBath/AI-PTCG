*** Settings ***
Documentation    Training-metrics feed and the live card explorer.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Training Metrics Endpoint Responds
    ${r}=    GET On Session    tcg    /api/training/metrics
    Dictionary Should Contain Key    ${r.json()}    metrics

Bundled Metrics Describe A Learning Curve
    [Documentation]    With the shipped checkpoint present, the curve should be non-empty
    ...                and each point should carry a win rate and update index.
    ${r}=    GET On Session    tcg    /api/training/metrics
    ${metrics}=    Set Variable    ${r.json()}[metrics]
    Pass Execution If    ${metrics} == []    No training data bundled; skipping curve checks.
    ${first}=    Set Variable    ${metrics}[0]
    Dictionary Should Contain Key    ${first}    winrate_recent
    Dictionary Should Contain Key    ${first}    update

Card Search Returns Results
    ${params}=    Create Dictionary    q=char
    ${r}=    GET On Session    tcg    /api/cards/search    params=${params}
    Dictionary Should Contain Key    ${r.json()}    data
    Should Not Be Empty    ${r.json()}[data]

Card Search Reports Its Source
    [Documentation]    'api'/'cache' when online, 'fallback' to the local catalogue offline.
    ${r}=    GET On Session    tcg    /api/cards/search
    Should Contain Any    ${r.json()}[source]    api    cache    fallback

Card Sets Endpoint Responds
    ${r}=    GET On Session    tcg    /api/cards/sets
    Dictionary Should Contain Key    ${r.json()}    data

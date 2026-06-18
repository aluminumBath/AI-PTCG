*** Settings ***
Documentation    Model explainer + easy export, and user card-image overrides.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Model Docs Explain Every Model
    ${r}=    GET On Session    tcg    /api/models/docs
    ${n}=    Get Length    ${r.json()}[models]
    Should Be True    ${n} >= 9
    ${mcts}=    Evaluate    [m for m in $r.json()['models'] if m['id']=='mcts'][0]
    Should Not Be Empty    ${mcts}[why]
    Should Not Be Empty    ${mcts}[how]
    Should Not Be Empty    ${mcts}[params]

Ensemble Agents Are Registered And Documented
    ${r}=    GET On Session    tcg    /api/agents
    ${ids}=    Evaluate    [m['id'] for m in $r.json()['models']]
    Should Contain    ${ids}    council
    Should Contain    ${ids}    prime
    Should Contain    ${ids}    meta_top3
    ${docs}=    GET On Session    tcg    /api/models/docs
    ${prime}=    Evaluate    [m for m in $docs.json()['models'] if m['id']=='prime'][0]
    Should Not Be Empty    ${prime}[why]
    Should Be Equal    ${prime}[family]    ensemble

Any Model Exports In One Call
    ${r}=    GET On Session    tcg    /api/models/ismcts/export
    Should Be Equal    ${r.json()}[model]    ismcts
    Should Not Be Empty    ${r.json()}[parameters]
    Should Not Be Empty    ${r.json()}[rationale]
    ${all}=    GET On Session    tcg    /api/models/export
    ${n}=    Get Length    ${all.json()}[models]
    Should Be True    ${n} >= 9

Card Image Override Set Apply And Clear
    ${body}=    Create Dictionary    url=https://example.com/charizard.png
    ${set}=    POST On Session    tcg    /api/cards/sv3-125/image    json=${body}
    Should Be Equal    ${set.json()}[image]    https://example.com/charizard.png
    ${qp}=    Create Dictionary    q=charizard
    ${search}=    GET On Session    tcg    /api/cards/search    params=${qp}
    ${hit}=    Evaluate    [c for c in $search.json()['data'] if c['id']=='sv3-125']
    Should Not Be Empty    ${hit}
    Should Be Equal    ${hit}[0][image]    https://example.com/charizard.png
    Should Be True    ${hit}[0][image_overridden]
    # cleanup
    ${del}=    DELETE On Session    tcg    /api/cards/sv3-125/image
    Should Be True    ${del.json()}[cleared]

Card Image Override Rejects Bad URL
    ${body}=    Create Dictionary    url=ftp://nope
    ${r}=    POST On Session    tcg    /api/cards/sv3-125/image    json=${body}    expected_status=400

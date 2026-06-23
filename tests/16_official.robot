*** Settings ***
Documentation     Official card data served from the database (empty-state contract).
Resource          resources/api.resource
Library           Collections
Suite Setup       Connect To API


*** Test Cases ***
Official Status Returns Counts
    ${r}=    GET On Session    tcg    /api/official/status    expected_status=200
    Dictionary Should Contain Key    ${r.json()}    cards
    Dictionary Should Contain Key    ${r.json()}    images
    Should Be True    ${r.json()}[cards] >= 0

Official Cards Search Returns A List
    ${r}=    GET On Session    tcg    /api/official/cards    params=q=pikachu    expected_status=200
    Dictionary Should Contain Key    ${r.json()}    cards
    ${cards}=    Set Variable    ${r.json()}[cards]
    Should Be True    isinstance($cards, list)

Official Missing Card Is 404
    GET On Session    tcg    /api/official/cards/999999    expected_status=404
    GET On Session    tcg    /api/official/cards/999999/image    expected_status=404

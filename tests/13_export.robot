*** Settings ***
Documentation     Kaggle exports: Simulation submission bundle + Strategy writeup.
Resource          resources/api.resource
Library           Collections
Suite Setup       Connect To API


*** Test Cases ***
Sim Export Returns A Gzip Bundle
    [Documentation]    submission.tar.gz with top-level main.py + deck.csv.
    ${p}=    Create Dictionary    deck=charizard_ex    agent=heuristic
    ${r}=    GET On Session    tcg    /api/competition/export/sim    params=${p}    expected_status=200
    Should Contain    ${r.headers}[Content-Type]    gzip
    Should Contain    ${r.headers}[Content-Disposition]    submission.tar.gz
    ${names}=    Evaluate
    ...    [m.name for m in __import__('tarfile').open(fileobj=__import__('io').BytesIO($r.content)).getmembers()]
    List Should Contain Value    ${names}    main.py
    List Should Contain Value    ${names}    deck.csv

Sim Bundle Members Are All Top Level
    [Documentation]    No nested directories — required by the submission format.
    ${p}=    Create Dictionary    deck=miraidon_ex    agent=ismcts
    ${r}=    GET On Session    tcg    /api/competition/export/sim    params=${p}    expected_status=200
    ${names}=    Evaluate
    ...    [m.name for m in __import__('tarfile').open(fileobj=__import__('io').BytesIO($r.content)).getmembers()]
    FOR    ${n}    IN    @{names}
        Should Not Contain    ${n}    /
    END

Sim Main Py Is Valid Python
    [Documentation]    The generated main.py must compile.
    ${p}=    Create Dictionary    deck=gardevoir_ex    agent=greedy
    ${r}=    GET On Session    tcg    /api/competition/export/sim    params=${p}    expected_status=200
    ${ok}=    Evaluate
    ...    (lambda s: (__import__('ast').parse(s) or True))(__import__('tarfile').open(fileobj=__import__('io').BytesIO($r.content)).extractfile('main.py').read().decode())
    Should Be True    ${ok}

Strategy Export Returns Markdown Under Word Limit
    [Documentation]    Writeup with rubric sections, custom title, <= 2000 words.
    ${p}=    Create Dictionary    deck=charizard_ex    agent=heuristic    title=Test Title    subtitle=A subtitle
    ${r}=    GET On Session    tcg    /api/competition/export/strategy    params=${p}    expected_status=200
    Should Contain    ${r.headers}[Content-Type]    markdown
    Should Contain    ${r.headers}[Content-Disposition]    writeup.md
    Should Contain    ${r.text}    \# Test Title
    Should Contain    ${r.text}    70%
    Should Contain    ${r.text}    20%
    Should Contain    ${r.text}    10%
    ${wc}=    Evaluate    len($r.text.split())
    Should Be True    ${wc} <= 2000

Export Rejects Unknown Deck
    ${p}=    Create Dictionary    deck=not_a_deck
    GET On Session    tcg    /api/competition/export/sim    params=${p}    expected_status=404
    GET On Session    tcg    /api/competition/export/strategy    params=${p}    expected_status=404

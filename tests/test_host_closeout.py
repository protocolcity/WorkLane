"""Host changes have verifiable artifacts without fabricated source commits."""
import pytest
from worklane.closeout_links import links_missing_landing_sha, closeout_links_violation
from worklane.mcp.handlers import TPHandlers, dispatch_tool


def test_host_exception_requires_both_labels_and_interactive_author():
    link='local/reports/verified-service.json'
    labels=['worker:you','you:host']
    assert links_missing_landing_sha(link,labels=labels,author='you') is None
    assert links_missing_landing_sha('done',labels=labels,author='you')
    for invalid in ([],['worker:you'],['you:host'],['worker:agent','you:host']):
        assert links_missing_landing_sha(link,labels=invalid,author='you')
    assert links_missing_landing_sha(link,labels=labels,author='agent')
    body='Completed: host repair\nVerification: verified configuration\nLinks: '+link
    assert closeout_links_violation(body,labels=labels,author='you') is None
    assert closeout_links_violation(body)


def test_legacy_handler_name_delegates_to_current_method(monkeypatch):
    handler=TPHandlers(author='you')
    monkeypatch.setattr(handler,'wl_show',lambda task_id,product=None:{'id':task_id,'project':product})
    assert handler.tp_show('wl-1',product='worklane')=={'id':'wl-1','project':'worklane'}
    result=dispatch_tool(handler,'tp_show',{'task_id':'tp-1','project':'worklane'})
    assert result['id']=='tp-1' and result['project']=='worklane'
    with pytest.raises(AttributeError):getattr(handler,'invented_method')

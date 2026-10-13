def bag_api(bags):
    """bags: {bag: [info-or-None, ...]}"""
    return {
        "GetContainerNumSlots": lambda b: len(bags.get(b, [])),
        "GetContainerItemInfo": lambda b, s: bags[b][s - 1],
    }


def stack(item, n):
    return {"itemID": item, "stackCount": n}


def test_counts_stacks_across_bags(addon):
    a = addon()
    a.mock("C_Container", bag_api({0: [stack(13444, 5)], 2: [None, stack(13444, 3)]}))
    assert a.eval("ns.Bags:Count(13444)") == 8
    assert a.eval("ns.Bags:Count(1)") == 0


def test_count_buff_sums_items(addon):
    a = addon()
    a.mock("C_Container", bag_api({0: [stack(1, 2), stack(2, 4), stack(3, 9)]}))
    assert a.eval("ns.Bags:CountBuff({items={1,2}})") == 6
    assert a.eval("ns.Bags:CountBuff({})") == 0


def test_missing_container_api_counts_zero(addon):
    a = addon()
    a.run("C_Container = nil")
    assert a.eval("ns.Bags:Count(13444)") == 0
    assert a.errors() == []


def test_nil_item_info_skipped(addon):
    a = addon()
    a.mock("C_Container", bag_api({0: [None, stack(7, 2), None]}))
    assert a.eval("ns.Bags:Count(7)") == 2


def test_rescan_on_bag_update_fires_event(addon):
    a = addon()
    bags = {0: [stack(7, 2)]}
    a.mock("C_Container", bag_api(bags))
    a.run("n = 0; ns.Events:On('FULLBUFF_BAGS', function() n = n + 1 end)")
    assert a.eval("ns.Bags:Count(7)") == 2
    a.run("n = 0")
    bags[0] = [stack(7, 6)]
    a.fire_event("BAG_UPDATE_DELAYED")
    a.fire_event("BAG_UPDATE_DELAYED")
    a.flush_timers()
    assert a.eval("n") == 1
    assert a.eval("ns.Bags:Count(7)") == 6

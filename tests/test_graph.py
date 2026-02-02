"""路徑規劃演算法測試"""
import pytest
from app.graph import Graph, Node2D, build_graph, dijkstra, astar, euclid
from app.models import MapData, Node, Edge


class TestEuclid:
    """歐幾里得距離測試"""

    def test_euclid_same_point(self):
        """測試同一點距離為 0"""
        a = Node2D(0, 0)
        b = Node2D(0, 0)
        assert euclid(a, b) == 0

    def test_euclid_horizontal(self):
        """測試水平距離"""
        a = Node2D(0, 0)
        b = Node2D(3, 0)
        assert euclid(a, b) == 3

    def test_euclid_vertical(self):
        """測試垂直距離"""
        a = Node2D(0, 0)
        b = Node2D(0, 4)
        assert euclid(a, b) == 4

    def test_euclid_diagonal(self):
        """測試對角距離 (3-4-5 三角形)"""
        a = Node2D(0, 0)
        b = Node2D(3, 4)
        assert euclid(a, b) == 5


class TestBuildGraph:
    """建立圖形測試"""

    def test_build_simple_graph(self):
        """測試建立簡單圖形"""
        map_data = MapData(
            map_id="test",
            nodes=[
                Node(id="A", x=0, y=0),
                Node(id="B", x=10, y=0),
            ],
            edges=[
                Edge(**{"from": "A", "to": "B"})
            ]
        )
        g = build_graph(map_data)

        assert "A" in g.nodes
        assert "B" in g.nodes
        assert len(g.adj["A"]) == 1
        assert len(g.adj["B"]) == 1  # bidirectional

    def test_build_graph_with_length(self):
        """測試有指定長度的邊"""
        map_data = MapData(
            map_id="test",
            nodes=[
                Node(id="A", x=0, y=0),
                Node(id="B", x=10, y=0),
            ],
            edges=[
                Edge(**{"from": "A", "to": "B", "length": 100})
            ]
        )
        g = build_graph(map_data)

        # 邊的長度應該是指定的 100，不是計算出來的 10
        assert g.adj["A"][0][1] == 100


class TestDijkstra:
    """Dijkstra 演算法測試"""

    @pytest.fixture
    def simple_graph(self):
        """建立簡單測試圖"""
        map_data = MapData(
            map_id="test",
            nodes=[
                Node(id="A", x=0, y=0),
                Node(id="B", x=10, y=0),
                Node(id="C", x=20, y=0),
            ],
            edges=[
                Edge(**{"from": "A", "to": "B", "length": 10}),
                Edge(**{"from": "B", "to": "C", "length": 10}),
            ]
        )
        return build_graph(map_data)

    def test_dijkstra_direct_path(self, simple_graph):
        """測試直接路徑"""
        path, dist = dijkstra(simple_graph, "A", "B")
        assert path == ["A", "B"]
        assert dist == 10

    def test_dijkstra_multi_hop(self, simple_graph):
        """測試多跳路徑"""
        path, dist = dijkstra(simple_graph, "A", "C")
        assert path == ["A", "B", "C"]
        assert dist == 20

    def test_dijkstra_same_node(self, simple_graph):
        """測試起點終點相同"""
        path, dist = dijkstra(simple_graph, "A", "A")
        assert path == ["A"]
        assert dist == 0

    def test_dijkstra_no_path(self):
        """測試無路徑情況"""
        map_data = MapData(
            map_id="test",
            nodes=[
                Node(id="A", x=0, y=0),
                Node(id="B", x=10, y=0),
            ],
            edges=[]  # 沒有邊
        )
        g = build_graph(map_data)

        with pytest.raises(ValueError, match="No path found"):
            dijkstra(g, "A", "B")


class TestAstar:
    """A* 演算法測試"""

    @pytest.fixture
    def grid_graph(self):
        """建立網格測試圖"""
        map_data = MapData(
            map_id="test",
            nodes=[
                Node(id="A", x=0, y=0),
                Node(id="B", x=10, y=0),
                Node(id="C", x=10, y=10),
                Node(id="D", x=0, y=10),
            ],
            edges=[
                Edge(**{"from": "A", "to": "B", "length": 10}),
                Edge(**{"from": "B", "to": "C", "length": 10}),
                Edge(**{"from": "A", "to": "D", "length": 10}),
                Edge(**{"from": "D", "to": "C", "length": 10}),
            ]
        )
        return build_graph(map_data)

    def test_astar_finds_path(self, grid_graph):
        """測試 A* 找到路徑"""
        path, dist = astar(grid_graph, "A", "C")
        assert path[0] == "A"
        assert path[-1] == "C"
        assert dist == 20  # 兩種路徑都是 20

    def test_astar_same_as_dijkstra(self, grid_graph):
        """測試 A* 與 Dijkstra 結果相同"""
        path_astar, dist_astar = astar(grid_graph, "A", "C")
        path_dijkstra, dist_dijkstra = dijkstra(grid_graph, "A", "C")

        # 距離應該相同
        assert dist_astar == dist_dijkstra

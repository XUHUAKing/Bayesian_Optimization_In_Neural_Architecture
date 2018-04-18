import networkx as nx
import numpy as np
import layer_graph as lg
from layer_graph import LAYERS
import ot


def get_path_length(g):
    '''
    compute path length

    args:
        g: layer_graph (assume that it has only one input layer and one output layer)

    return:
        res: dictionary of average of path length
        ###following terms are no longer available###
        rw_ip: random walk distance for input layer
        rw_op: random walk distance for output layer
        sp_ip: shortest path for input layer
        sp_op: shortest path for output layer
        lp_ip: longest path for input layer
        lp_op: longest path for output layer
    '''

    rw_ip = {}
    rw_op = {}
    sp_ip = {}
    sp_op = {}
    lp_ip = {}
    lp_op = {}
    res = {}

    graph = g.get_graph()
    nodes = list(g.get_nodes())

    rw_ip[nodes[0]] = 0
    sp_ip[nodes[0]] = 0
    lp_ip[nodes[0]] = 0
    rw_op[nodes[-1]] = 0
    sp_op[nodes[-1]] = 0
    lp_op[nodes[-1]] = 0

    for node in nodes[1:]:
        rw_data = []
        sp_data = []
        lp_data = []
        for p in graph.predecessors(node):
            rw_data.append(rw_ip[p])
            sp_data.append(sp_ip[p])
            lp_data.append(lp_ip[p])
        rw_ip[node] = 1 + np.mean(rw_data)
        sp_ip[node] = 1 + np.min(sp_data)
        lp_ip[node] = 1 + np.max(lp_data)

    for node in reversed(nodes[:-1]):
        rw_data = []
        sp_data = []
        lp_data = []
        for p in graph.successors(node):
            rw_data.append(rw_op[p])
            sp_data.append(sp_op[p])
            lp_data.append(lp_op[p])
        rw_op[node] = 1 + np.mean(rw_data)
        sp_op[node] = 1 + np.min(sp_data)
        lp_op[node] = 1 + np.max(lp_data)

    for node in nodes:
        res[node] = (rw_ip[node] + rw_op[node] + sp_ip[node] + \
                        sp_op[node] + lp_ip[node] + lp_op[node]) / 6

    return res


def get_lmm_matrix(g1, g2):
    '''
        Get argumented lmm
    '''
    '''
    Construct cost matrix
    When indexing M by enum type, remember minus it by 1 (enum starts from 1)
    '''
    M = np.ones((lg.layers_type_num, lg.layers_type_num)) * 3 # Inf should be any value larger than 2
    np.fill_diagonal(M, 0)
    M[LAYERS.conv3.value - 1, LAYERS.conv5.value - 1] = 0.2
    M[LAYERS.conv3.value - 1, LAYERS.conv7.value - 1] = 0.3
    M[LAYERS.conv5.value - 1, LAYERS.conv7.value - 1] = 0.2
    M[LAYERS.maxpool.value - 1, LAYERS.avgpool.value - 1] = 0.25
    M = np.triu(M)
    M += M.T - np.diag(M.diagonal())
    #Construct penality matrix
    C = np.zeros((g1.get_num_layers() + 1, g2.get_num_layers() + 1))
    for c1, n1 in enumerate(g1.get_nodes()):
        for c2, n2 in enumerate(g2.get_nodes()):
            C[c1, c2] = M[g1.get_node_attr(n1).value - 1, g2.get_node_attr(n2).value - 1]
    return C

def get_nas_matrix(g1, g2):
    C = np.zeros((g1.get_num_layers() + 1, g2.get_num_layers() + 1))
    C[g1.get_num_layers(), 0:-1] = np.ones((g2.get_num_layers()))
    C[0:-1, g2.get_num_layers()] = np.ones((g1.get_num_layers()))
    return C

def get_str_matrix(g1, g2):
    C = np.zeros((g1.get_num_layers() + 1, g2.get_num_layers() + 1))
    special_layers = [[LAYERS.conv3, LAYERS.conv5, LAYERS.conv7], [LAYERS.maxpool, LAYERS.avgpool], \
                       [LAYERS.fc]]
    pl_1 = get_path_length(g1)
    pl_2 = get_path_length(g2)
    for c1, n1 in enumerate(g1.get_nodes()):
        for c2, n2 in enumerate(g2.get_nodes()):
            C[c1, c2] = abs(pl_1[c1] - pl_2[c2])
            for sl in special_layers:
                a = 0
                b = 0
                if g1.get_node_attr(n1) in sl:
                    a = pl_1[c1]
                if g2.get_node_attr(n2) in sl:
                    b = pl_2[c2]
                C[c1, c2] += abs(a - b)
    C /= 1 + len(special_layers)
    return C
    
def get_distance(g1, g2, v_str=0.5):
    '''
    return :
        d, d_bar
    '''
    C = get_lmm_matrix(g1, g2) + get_nas_matrix(g1, g2) + v_str * get_str_matrix(g1, g2)
    y1 = np.zeros((g1.get_num_layers() + 1))
    y2 = np.zeros((g2.get_num_layers() + 1))
    for i, node in enumerate(g1.get_nodes()):
        y1[i] = g1.get_node_attr(node, 'layer_mass')
    y1[g1.get_num_layers()] = g2.get_total_mass()
    for i, node in enumerate(g2.get_nodes()):
        y2[i] = g2.get_node_attr(node, 'layer_mass')
    y2[g2.get_num_layers()] = g1.get_total_mass()
    d = ot.emd2(y1, y2, C)
    d_bar = d / (g1.get_total_mass() + g2.get_total_mass())
    return d, d_bar

if __name__ == '__main__':
    G = lg.Layer_graph(235)
    G.add_node(LAYERS.ip)
    G.add_node(LAYERS.conv3, 16)
    G.add_node(LAYERS.conv3, 16)
    G.add_node(LAYERS.conv3, 32)
    G.add_node(LAYERS.conv5, 32)
    G.add_node(LAYERS.maxpool)
    G.add_node(LAYERS.fc, 16)
    G.add_node(LAYERS.softmax)
    G.add_node(LAYERS.op)
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(3, 4)
    G.add_edge(4, 5)
    G.add_edge(5, 6)
    G.add_edge(6, 7)
    G.add_edge(7, 8)
    G.update_lm()
    G1 = lg.Layer_graph(1)
    G1.add_node(LAYERS.ip)
    G1.add_node(LAYERS.conv3, 16)
    G1.add_node(LAYERS.conv3, 16)
    G1.add_node(LAYERS.conv3, 16)
    G1.add_node(LAYERS.conv3, 16)
    G1.add_node(LAYERS.conv5, 32)
    G1.add_node(LAYERS.maxpool)
    G1.add_node(LAYERS.fc, 16)
    G1.add_node(LAYERS.softmax)
    G1.add_node(LAYERS.op)
    G1.add_edge(0, 1)
    G1.add_edge(1, 2)
    G1.add_edge(2, 4)
    G1.add_edge(1, 3)
    G1.add_edge(3, 5)
    G1.add_edge(4, 5)
    G1.add_edge(5, 6)
    G1.add_edge(6, 7)
    G1.add_edge(7, 8)
    G1.add_edge(8, 9)
    G1.update_lm()
    G2 = lg.Layer_graph(1)
    G2.add_node(LAYERS.ip)
    G2.add_node(LAYERS.conv7, 16)
    G2.add_node(LAYERS.conv5, 32)
    G2.add_node(LAYERS.conv3, 16)
    G2.add_node(LAYERS.conv3, 16)
    G2.add_node(LAYERS.avgpool)
    G2.add_node(LAYERS.maxpool)
    G2.add_node(LAYERS.maxpool)
    G2.add_node(LAYERS.fc, 16)
    G2.add_node(LAYERS.conv3, 16)
    G2.add_node(LAYERS.softmax)
    G2.add_node(LAYERS.maxpool)
    G2.add_node(LAYERS.fc, 16)
    G2.add_node(LAYERS.softmax)
    G2.add_node(LAYERS.op)
    G2.add_edge(0, 1)
    G2.add_edge(1, 2)
    G2.add_edge(2, 5)
    G2.add_edge(5, 8)
    G2.add_edge(8, 10)
    G2.add_edge(8, 13)
    G2.add_edge(10, 14)
    G2.add_edge(13, 14)
    G2.add_edge(1, 3)
    G2.add_edge(3, 6)
    G2.add_edge(6, 12)
    G2.add_edge(12, 13)
    G2.add_edge(1, 4)
    G2.add_edge(4, 7)
    G2.add_edge(7, 9)
    G2.add_edge(9, 11)
    G2.add_edge(11, 12)
    G2.update_lm()
    import distance
    print(distance.get_distance(G, G1))
    print(distance.get_distance(G1, G, 1))
    print(distance.get_distance(G, G2))
    print(distance.get_distance(G1, G2))
# Arrays and linked lists
An array stores elements next to each other in memory, so reading element i is O(1).
Inserting in the middle of an array is O(n) because later elements must shift.
A linked list stores nodes with pointers; inserting after a known node is O(1) but finding the i-th element is O(n).

# Hash tables
A hash table maps keys to buckets with a hash function, giving average O(1) lookup, insert and delete.
Collisions happen when two keys land in the same bucket; chaining keeps a list per bucket, open addressing probes for a free slot.
When the load factor grows too high, the table is resized and every key is rehashed.

# Binary search trees
In a binary search tree every key in the left subtree is smaller than the node and every key in the right subtree is larger.
Search, insert and delete take O(h) where h is the height. A balanced tree (AVL, red-black) keeps h at O(log n);
inserting sorted keys into a plain BST makes it a chain with height n.

# Heaps
A binary heap is a complete tree stored in an array where each parent is no larger than its children (min-heap).
Reading the minimum is O(1); push and pop are O(log n) because an element sifts up or down one level at a time.
Heaps implement priority queues, used for example in Dijkstra's shortest path algorithm.

# Graph traversal
Breadth-first search uses a queue and visits nodes in order of distance in edges, so it finds shortest paths in unweighted graphs.
Depth-first search uses a stack (or recursion) and goes as deep as possible before backtracking; it is used for cycle detection
and topological sorting. Both run in O(V + E) with an adjacency list.

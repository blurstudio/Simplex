import numpy as np

def rigidAlign(P, Q, iters=10):
	'''
		Rigidly (with non-uniform scale) align meshes with matching vert order
		by a least-squares error. Uses a variation of an algorithm by Umeyama
		Relevant links:
		  - https://gist.github.com/nh2/bc4e2981b0e213fefd4aaa33edfb3893 (this code)
		  - http://stackoverflow.com/a/32244818/263061 (solution with scale)

		Arguments:
			P (N*3 numpy array): The ground truth vertices we're trying to match
			Q (N*3 numpy array): The transformed vertices
			iters (int): The number of iterations. You really shouldn't need more than 10

		Returns:
			(4*4 np.array): The transformation matrix that most closely aligns Q to P
	'''
	#pylint:disable=invalid-name
	assert P.shape == Q.shape

	n, dim = P.shape
	assert dim == 3

	if iters <= 1:
		raise ValueError("Must run at least 1 iteration")

	# Get the centroid of each object
	Qm = Q.mean(axis=0)
	Pm = P.mean(axis=0)

	# Subtract out the centroid to get the basic aligned mesh
	cP = P - Pm # centeredP
	cQRaw = Q - Qm # centeredQ

	cQ = cQRaw.copy()
	cumulation = np.eye(3) #build an accumulator for the rotation

	# Here, we find an approximate rotation and scaling, but only
	# keep track of the accumulated rotations.
	# Then we apply the non-uniform scale by comparing bounding boxes
	# This way we don't get any shear in our matrix, and we relatively
	# quickly walk our way towards a minimum
	for _ in xrange(iters):
		# Magic?
		C = np.dot(cP.T, cQ) / n
		V, S, W = np.linalg.svd(C)

		# Handle negative scaling
		d = (np.linalg.det(V) * np.linalg.det(W)) < 0.0
		if d:
			S[-1] = -S[-1]
			V[:, -1] = -V[:, -1]

		# build the rotation matrix for this iteration
		# and add it to the accumulation
		R = np.dot(V, W)
		cumulation = np.dot(cumulation, R.T)

		# Now apply the accumulated rotation to the raw point positions
		# Then grab the non-uniform scaling from the bounding box
		# And set up cQ for the next iteration
		cQ = np.dot(cQRaw, cumulation)
		sf = (cP.max(axis=0) - cP.min(axis=0)) / (cQ.max(axis=0) - cQ.min(axis=0))
		cQ = cQ * sf

	# Build the final transformation
	csf = cumulation * sf
	tran = Pm - Qm.dot(csf)
	outMat = np.eye(4)
	outMat[:3, :3] = csf
	outMat[3, :3] = tran
	return outMat


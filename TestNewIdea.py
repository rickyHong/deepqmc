import numpy as np
import matplotlib.pyplot as plt
import time

import torch
import torch.nn as nn
from torch.autograd import Variable,grad
import torch.nn.functional as F
import copy

cmap=plt.get_cmap("plasma")


test = torch.tensor([[-1,-1],[-1,-1],[-1,-1],[-1,-1],[0,0],[0,0],[0,0.1],[1,0],[1,1],[-1,1],[-1,-1]]).type(torch.FloatTensor)
obj = (slice(1,10,5), slice(None,None,1))
print(test[obj])

exit(0)


f = lambda x,a: torch.exp(-1/2*(x-a)**2/0.01)/np.sqrt(2*np.pi)
f2d = lambda x,a: torch.exp(-1/2*torch.norm(x[:,None,None]-a[None,:,:],dim=-1)**2/0.01)/np.sqrt(2*np.pi)
fnd = lambda x,a: torch.exp(-1/2*torch.norm(x[:,None,None]-a[None,:,:],dim=-1)**2/0.01)/np.sqrt(2*np.pi)

#def almost_sigmoid(x,a,x0,x1):
#	return a*(x-x0)/torch.sqrt(a**2*(x-x0)**2+1)-a*(x-x1)/torch.sqrt(a**2*(x-x1)**2+1)



def myhist(X,min=-0.5,max=0.5,bins=30):
	res = torch.zeros(size=(bins,))
	B=np.linspace(min,max,bins)
	for i in range(bins):
		res[i] = torch.sum(f(X,B[i]))
	return res/torch.sum(res)
	
def myhist2D(X,min=-2,max=2,bins=30):
	B=np.array(np.meshgrid(np.linspace(min,max,bins),np.linspace(min,max,bins))).swapaxes(0,-1)
	B2 = torch.from_numpy(B).type(torch.FloatTensor)
	res = torch.sum(f2d(X,B2),dim=0)
	return res/torch.sum(res)

def myhistND(X,min,max,bins):
	B=torch.from_numpy(np.array(np.meshgrid(*[np.linspace(min,max,bins) for i in range(X.shape[-1])])).swapaxes(0,-1)).type(torch.FloatTensor)
	res = torch.sum(fnd(X,B),dim=0)
	return res/torch.sum(res)


#test = torch.tensor([[-1,-1],[-1,-1],[-1,-1],[-1,-1],[0,0],[0,0],[0,0.1],[1,0],[1,1],[-1,1],[-1,-1]]).type(torch.FloatTensor)
#plt.imshow(myhist2D(test))
#plt.show()
#exit(0)

class Samplenet(nn.Module):
	def __init__(self):
		super(Samplenet, self).__init__()
		self.NN=nn.Sequential(
				torch.nn.Linear(2000, 200),
				torch.nn.ReLU(),
				torch.nn.Linear(200, 200),
				torch.nn.ReLU(),
				torch.nn.Linear(200, 200),
				torch.nn.ReLU(),
				torch.nn.Linear(200, 2000)
				)

	def forward(self,x):
		return self.NN(x)

class Wavenet(nn.Module):
	def __init__(self):
		super(Wavenet, self).__init__()
		self.NN=nn.Sequential(
				torch.nn.Linear(2, 64),
				torch.nn.ELU(),
				torch.nn.Linear(64, 64),
				torch.nn.ELU(),
				torch.nn.Linear(64, 64),
				torch.nn.ELU(),
				torch.nn.Linear(64, 1)
				)
		#self.Lambda=nn.Parameter(torch.Tensor([-1]))	#eigenvalue

	def forward(self,x):
		d = torch.zeros(len(x),2)
		d[:,0] = torch.norm(x-R1,dim=1)
		d[:,1] = torch.norm(x-R2,dim=1)
		r = torch.erf(d/0.5)/d
		return self.NN(r)


LR=0.001
net  = Samplenet()#
net2 = Wavenet()
R1 = torch.tensor([-1,0]).type(torch.FloatTensor)
R2 = torch.tensor([1,0]).type(torch.FloatTensor)

params = [p for p in net.parameters()]
opt = torch.optim.Adam(params, lr=LR)

params2 = [p for p in net2.parameters()]
opt2 = torch.optim.Adam(params2, lr=LR)

epochs = 3
steps  = 100
steps2 = 45
batch_size = 100
ran = (-5,5)

f = lambda x: net2(x)**2

x,y = torch.meshgrid([torch.linspace(ran[0],ran[1],100),torch.linspace(ran[0],ran[1],100)])
G=torch.cat((x,y)).view(2,100,100).transpose(0,-1)
P=np.zeros((100,100))
for i in range(100):

	P[i] = f(G[i]).detach().numpy().flatten()

j=0 #delete later just for plots

for epoch in range(epochs):

	start = time.time()



	if epoch==0:
		X_all = torch.from_numpy(np.random.normal(0,1,(batch_size*steps,2))*3).type(torch.FloatTensor)

	else:
		X_all = torch.zeros(size=(steps*batch_size,2))
		for i in range(steps*batch_size//1000):
			X_i = net(torch.rand(2000).view(1,-1)).detach().flatten().reshape(1000,2)
			X_all[i*1000:(i+1)*1000] = X_i
			
	
	#check if reintializing is better than keeping (would expect keeping is better in higher dimensions) 
	net  = Samplenet()
	params = [p for p in net.parameters()]
	opt = torch.optim.Adam(params, lr=LR)

	index = torch.randperm(steps*batch_size)
	X_all.requires_grad = True

	for step in range(steps):


		X = X_all[index[step*batch_size:(step+1)*batch_size]]

		r1    = torch.norm(X-R1,dim=1)
		r2    = torch.norm(X-R2,dim=1)

		V     = -1/r1 -1/r2

		Psi=net2(X).flatten()

		g = torch.autograd.grad(Psi,X,create_graph=True,retain_graph=True,grad_outputs=torch.ones(batch_size))[0]
		gradloss  = torch.sum(0.5*(torch.sum(g**2,dim=1)) + Psi**2*V)/torch.sum(Psi**2)
		J = gradloss + (torch.sum(Psi**2)-1)**2


		opt2.zero_grad()
		J.backward()
		opt2.step()


		print("Progress {:2.0%}".format(step /steps), end="\r")
	print("\n")
	x,y = torch.meshgrid([torch.linspace(ran[0],ran[1],100),torch.linspace(ran[0],ran[1],100)])
	G=torch.cat((x,y)).view(2,100,100).transpose(0,-1)
	P=np.zeros((100,100))
	for i in range(100):

		P[i] = f(G[i]).detach().numpy().flatten()
	
	P=P/np.sum(P)

	plt.subplot2grid((3,4),(epoch,0))
	plt.imshow(P,extent=[ran[0],ran[1],ran[0],ran[1]],cmap=cmap)
	
	Z = torch.from_numpy(P).type(torch.FloatTensor)
	


	for i in range(steps2):

		print("Progress {:2.0%}".format(i /steps2), end="\r")
		X = torch.rand(2000).view(1,-1)
		Y = net(X).flatten().reshape(1000,2)
		Ya = myhist2D(Y.flip(dims=(-1,)),ran[0],ran[1],100)
		#print(torch.sum((Y>ran[1]).type(torch.FloatTensor)*(Y-ran[1])**2))

		ll = torch.sum((Y[:,0]>ran[1]).type(torch.FloatTensor)*(Y[:,0]-ran[1])**2)+torch.sum((Y[:,1]>ran[1]).type(torch.FloatTensor)*(Y[:,1]-ran[1])**2)
		ls = torch.sum((Y[:,0]<ran[0]).type(torch.FloatTensor)*(Y[:,0]-ran[0])**2)+torch.sum((Y[:,1]<ran[0]).type(torch.FloatTensor)*(Y[:,1]-ran[0])**2)
		J = torch.sum((Ya-Z)**2)+ll+ls
		opt.zero_grad()
		J.backward(retain_graph=True)
		opt.step()

		if (i+1)%15==0 and i!=0:
			plt.subplot2grid((3,4),(j//3,(j%3)+1))
			plt.imshow(Ya.detach().numpy(),extent=[ran[0],ran[1],ran[0],ran[1]],cmap=cmap)
			plt.title("iterations = "+str(i+1))
			j+=1
			
			
		#	ax1.plot(np.linspace(ran[0],ran[1],100),Ya.detach().numpy(),label=str(i+1),ls=':')
	#ax1.legend()
	#ax2.imshow(Ya.detach().numpy(),extent=[ran[0],ran[1],ran[0],ran[1]],cmap=cmap)
	#ax2.hist(Y.detach().numpy(),bins=100,density=True)
	#plt.setp(ax1.get_xticklabels(), fontsize=6)	
	

	print('___________________________________________')
	print('It took', time.time()-start, 'seconds.')
	print('\n')
plt.show()


#X_plot = torch.linspace(-5,5,100)
#Y_plot = net2(X_plot.view(-1,1))**2
#plt.plot(X_plot.detach().numpy(),Y_plot.detach().numpy())
#plt.hist(Y.detach().numpy(),bins=100,density=True)




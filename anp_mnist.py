"""Script that applies ANP to the MNIST dataset."""

import os
import sys
import torch
from matplotlib import pyplot as plt
import mnist
import random
import numpy as np

# Provide access to modules in repo.
sys.path.insert(0, os.path.abspath('neural_process_models'))

from neural_process_models.anp import ANP_Model


# Retrieve 10000 test data points from MNIST.

test_images = mnist.test_images()  # (10000 x 28 x 28)
test_images = (test_images / 255.0)  # normalize pixel values

data_size = len(test_images)
test_images = np.resize(test_images, (10000, 28, 28, 1))

print("Retrieved and prepared data. Training...")


# Initialize model, hyperparameters

model = ANP_Model(x_dim=2,	# x_dim: normalized pixel index (0-1 x 0-1)
			      y_dim=1,	# y_dim: normalized pixel value (0-1)
			      mlp_hidden_size_list=[256, 256, 256, 256],
			      latent_dim=256,
			      use_rnn=False,
			      use_self_attention=False,
			      use_deter_path=True,
			      self_attention_type="dot",
			      cross_attention_type="dot")#.cuda()

optim = torch.optim.Adam(model.parameters(), lr=1e-4)

num_epochs = 10000
batch_size = 16
num_context = 400

# Train model; display results

# avg_loss_list = []

for epoch in range(1, num_epochs + 1):
    print("step = " + str(epoch))

    model.train()

    plt.clf()
    optim.zero_grad()

    ctt_x, ctt_y, tgt_x, tgt_y = list(), list(), list(), list()

    sample_context_indices = random.sample(range(data_size), batch_size)

    for context_idx in sample_context_indices:
    	pixel_indices = random.sample(range(784), num_context)

    	c_x, c_y = list(), list()
    	for pixel_idx in pixel_indices:
    		pixel_x = (pixel_idx // 28)
    		pixel_y = (pixel_idx % 28)

    		c_x.append([pixel_x, pixel_y])
    		c_y.append(test_images[context_idx][pixel_x][pixel_y])

    	ctt_x.append(c_x)
    	ctt_y.append(c_y)

    sample_target_indices = random.sample(range(data_size), batch_size)

    for target_idx in sample_target_indices:
        t_x, t_y = list(), list()
        for pixel_x in range(28):
        	for pixel_y in range(28):
	            t_x.append([pixel_x, pixel_y])
	            t_y.append(test_images[target_idx][pixel_x][pixel_y])

        tgt_x.append(t_x)
        tgt_y.append(t_y)

    ctt_x = torch.FloatTensor(ctt_x)#.cuda()
    ctt_y = torch.FloatTensor(ctt_y)#.cuda()
    tgt_x = torch.FloatTensor(tgt_x)#.cuda()
    tgt_y = torch.FloatTensor(tgt_y)#.cuda()


    # ctt_x: (batch_size x num_context x 2), ctt_y: (batch_size x 784 x 1)
    # tgt_x: (batch_size x num_context x 2), tgt_y: (batch_size x 784 x 1)
    mu, sigma, log_p, kl, loss = model(ctt_x, ctt_y, tgt_x, tgt_y)

    # print('kl =', kl)
    print('loss = ', loss)
    # print('mu.size() =', mu.size())
    # print('sigma.size() =', sigma.size())

    # tgt_x_np = tgt_x[0, :, :].squeeze(-1).numpy()
    # print('tgt_x_np.shape =', tgt_x_np.shape)

    """
    if epoch == 1:
        avg_loss_list.append(loss.item())
    else:
    	avg_loss_list.append(((epoch - 1) * avg_loss_list[-1] + loss.item()) / epoch)
    """

    loss.backward()
    optim.step()

    model.eval()
    plt.ion()
    # fig = plt.figure()
    
    # Visualize first target image.
    pred_y = mu[0].view(28, 28).detach().numpy()

    plt.axis('off')
    #plt.imshow(torch.sigmoid(tgt_y).squeeze(0).view(-1, 28).detach().numpy())
    #plt.imshow(pred_y)

    """
    if epoch % 1000 == 0:
        target_indices = random.sample(range(mu.size()[0]), 20)
        for idx in target_indices:
            title_str = 'Training at epoch ' + str(epoch) + ', image ' + str(idx)
            plt.title(title_str)
            pred_y = mu[idx].view(28, 28).detach().cpu().numpy()
            plt.imshow(pred_y)
            plt.savefig("../results/" + str(epoch) + "/" + title_str + ".png")

        torch.save({'model':model.state_dict(),
                    'optimizer':optim.state_dict()},
                    os.path.join('./checkpoints','checkpoint_%d.pth.tar' % epoch))
	"""

    plt.pause(0.1)

plt.ioff()
plt.show()

"""
with open("../results/loss.txt", "w+") as outfile:
    outfile.write("[")
    for i in range(len(avg_loss_list) - 1):
        outfile.write(str(avg_loss_list[i]) + ", ")
    outfile.write(str(avg_loss_list[-1]))
    outfile.write("]")
"""